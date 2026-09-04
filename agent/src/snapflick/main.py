"""API FastAPI. Cumple el contrato de AgentCore: /invocations y /ping en :8080."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .job_store import get_job_store
from .model_provider import warmup_model
from .models.schemas import Job, JobStatus
from .paths import background_key, catalog_dir, upload_original_dir
from .pipeline import (
    KEEP_ORIGINAL_BACKGROUND,
    add_product_to_job,
    recompose_product_background,
    run_job,
)
from .tools.catalog_tools import export_catalog_json, render_catalog_html
from .tools.image_tools import _get_session as _get_rembg_session
from .tools.storage_tools import get_storage

log = logging.getLogger(__name__)

# Bucle de eventos de uvicorn, capturado en el lifespan de abajo. `_notify_change`
# se llama desde hilos de worker (BackgroundTasks, rutas sync) que no son ese
# bucle, así que necesita la referencia para poder agendar los `broadcast_*`
# (coroutines) con `asyncio.run_coroutine_threadsafe`.
_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="SnapFlick", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA = Path(settings.data_dir)
DATA.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(DATA)), name="files")

STORE = get_job_store()  # SQLite local, o S3 (jobs/<id>.json) con SNAPFLICK_S3_BUCKET
JOBS: dict[str, Job] = {j.id: j for j in STORE.all()}  # caché en memoria; STORE es la fuente


# Sentinel de `background_key` para "blanco, explícitamente elegido por el
# usuario" — distinto de `None`/ausente, que en `create_job` cae de vuelta al
# fondo marcado como "Por defecto" (ver `_get_default_background_key`). Sin
# esto, "Blanco" y "no elegí nada" serían indistinguibles en el payload y un
# click explícito en "Blanco" terminaría aplicando el fondo por defecto de
# todos modos.
EXPLICIT_WHITE_BACKGROUND = "__white__"


def _resolve_background_path(key: str | None) -> str | None:
    """Convierte un `background_key` guardado (p.ej. `"abc123_playa.jpg"`, tal
    como lo devuelve `GET /backgrounds`) en el path de filesystem bajo DATA.

    `KEEP_ORIGINAL_BACKGROUND` y `EXPLICIT_WHITE_BACKGROUND` son sentinels, no
    keys guardadas — el primero se devuelve tal cual para que `pipeline.py` lo
    reconozca, el segundo se resuelve a `None` (blanco)."""
    if not key:
        return None
    if key == KEEP_ORIGINAL_BACKGROUND:
        return KEEP_ORIGINAL_BACKGROUND
    if key == EXPLICIT_WHITE_BACKGROUND:
        return None
    return str(DATA / background_key(key))


def _background_key_url(key: str | None) -> str | None:
    """Como `_to_url`, pero preserva `KEEP_ORIGINAL_BACKGROUND` en vez de
    tratarlo como un path de filesystem (no lo es, así que `_to_url` lo
    convertiría en `None` y el frontend perdería la distinción entre "sin
    fondo elegido" y "mantener el fondo original")."""
    if key == KEEP_ORIGINAL_BACKGROUND:
        return KEEP_ORIGINAL_BACKGROUND
    return _to_url(key)


_DEFAULT_BACKGROUND_STORAGE_KEY = "backgrounds/_default.json"


def _get_default_background_key() -> str | None:
    """Key del fondo guardado marcado como "Por defecto" (ver `PUT
    /backgrounds/default`), o `None` si no se marcó ninguno. Se guarda como un
    JSON chico en `Storage` (no en `Job`/SQLite) porque es un ajuste del pool
    de fondos compartido entre jobs, no de un job en particular."""
    storage = get_storage()
    if not storage.exists(_DEFAULT_BACKGROUND_STORAGE_KEY):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "default.json"
        storage.fetch(_DEFAULT_BACKGROUND_STORAGE_KEY, str(dest))
        data = json.loads(dest.read_text(encoding="utf-8"))
        return data.get("background_key")


def _set_default_background_key(key: str | None) -> None:
    storage = get_storage()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "default.json"
        src.write_text(json.dumps({"background_key": key}), encoding="utf-8")
        storage.save(str(src), _DEFAULT_BACKGROUND_STORAGE_KEY)


def _relative_key(path: str) -> str | None:
    """Path absoluto de filesystem (bajo DATA) -> key relativo, o None si está fuera de DATA."""
    try:
        return Path(path).resolve().relative_to(DATA.resolve()).as_posix()
    except ValueError:
        return None


def _to_url(path: str | None) -> str | None:
    """Convierte un path absoluto de filesystem (bajo DATA) en una URL pública.

    Los paths que guarda `Job` son siempre paths locales bajo DATA, porque
    `pipeline.py` los necesita ahí para abrir archivos con Pillow/rembg. Esta
    capa HTTP es la que decide cómo servirlos: con `SNAPFLICK_S3_BUCKET` sin
    setear, vía `/files/...` (StaticFiles); con el bucket seteado, vía la URL
    firmada de S3 que ya subió `_sync_job_to_storage`.
    """
    if not path:
        return None
    rel = _relative_key(path)
    if rel is None:
        return None
    if settings.s3_bucket:
        return get_storage().url(rel)
    return f"/files/{rel}"


def _sync_job_to_storage(job: Job) -> None:
    """Sube los artefactos del job a S3 cuando SNAPFLICK_S3_BUCKET está seteado.

    El procesamiento siempre escribe primero en disco local bajo DATA (rembg y
    Pillow necesitan paths de filesystem); esto replica el resultado a S3 para
    que `_to_url` pueda servirlo desde ahí. Sin bucket seteado, es un no-op y
    todo se sirve directamente desde disco local vía /files.
    """
    if not settings.s3_bucket:
        return
    storage = get_storage()
    candidates = [job.background_key, job.catalog_html_path, job.catalog_json_path]
    for record in job.products:
        img = record.image
        candidates += [img.source_path, img.cutout_path, img.composed_path, img.thumbnail_path]
        candidates.append(record.background_key)
    for path in candidates:
        if not path:
            continue
        rel = _relative_key(path)
        if rel is None:
            continue
        try:
            storage.save(path, rel)
        except Exception:
            log.exception("No se pudo subir %s a S3 (bucket=%s)", path, settings.s3_bucket)


def job_to_public_dict(job: Job) -> dict:
    data = job.model_dump(mode="json")
    data["background_key"] = _background_key_url(job.background_key)
    data["catalog_html_path"] = _to_url(job.catalog_html_path)
    data["catalog_json_path"] = _to_url(job.catalog_json_path)
    for product, record in zip(data["products"], job.products, strict=True):
        img = product["image"]
        img["source_path"] = _to_url(record.image.source_path)
        img["cutout_path"] = _to_url(record.image.cutout_path)
        img["composed_path"] = _to_url(record.image.composed_path)
        img["thumbnail_path"] = _to_url(record.image.thumbnail_path)
        product["background_key"] = _background_key_url(record.background_key)
    return data


def _cover_thumbnail(job: Job) -> str | None:
    for record in job.products:
        thumb = _to_url(record.image.thumbnail_path or record.image.composed_path)
        if thumb:
            return thumb
    return None


def _job_summaries() -> list[dict]:
    return [
        {
            "id": j.id,
            "status": j.status,
            "products": len(j.products),
            "created_at": j.created_at.isoformat(),
            "catalog_title": j.plan.catalog_title if j.plan else None,
            "catalog_html_path": _to_url(j.catalog_html_path),
            "thumbnail_url": _cover_thumbnail(j),
        }
        for j in sorted(JOBS.values(), key=lambda j: j.created_at, reverse=True)
    ]


class ConnectionManager:
    """Suscriptores WebSocket de `/ws/jobs` (lista) y `/ws/jobs/{id}` (un job).

    Reemplaza el polling que hacía el frontend (`useJobs`/`useJob` con
    `refreshInterval`): en vez de que cada cliente pregunte cada 2-5s, el
    servidor empuja el estado nuevo solo cuando algo cambia de verdad.
    """

    def __init__(self) -> None:
        self.list_subscribers: set[WebSocket] = set()
        self.job_subscribers: dict[str, set[WebSocket]] = {}

    async def connect_list(self, ws: WebSocket) -> None:
        await ws.accept()
        self.list_subscribers.add(ws)
        await ws.send_json(_job_summaries())

    def disconnect_list(self, ws: WebSocket) -> None:
        self.list_subscribers.discard(ws)

    async def connect_job(self, ws: WebSocket, job_id: str) -> None:
        await ws.accept()
        self.job_subscribers.setdefault(job_id, set()).add(ws)
        if job_id in JOBS:
            await ws.send_json(job_to_public_dict(JOBS[job_id]))

    def disconnect_job(self, ws: WebSocket, job_id: str) -> None:
        subs = self.job_subscribers.get(job_id)
        if not subs:
            return
        subs.discard(ws)
        if not subs:
            del self.job_subscribers[job_id]

    async def broadcast_list(self) -> None:
        if not self.list_subscribers:
            return
        data = _job_summaries()
        dead = {ws for ws in self.list_subscribers if not await _try_send(ws, data)}
        self.list_subscribers -= dead

    async def broadcast_job(self, job_id: str) -> None:
        subs = self.job_subscribers.get(job_id)
        if not subs or job_id not in JOBS:
            return
        data = job_to_public_dict(JOBS[job_id])
        dead = {ws for ws in subs if not await _try_send(ws, data)}
        subs -= dead


async def _try_send(ws: WebSocket, data: object) -> bool:
    try:
        await ws.send_json(data)
        return True
    except Exception:
        return False


manager = ConnectionManager()


def _notify_change(job_id: str) -> None:
    """Agenda el broadcast de `job_id` (y de la lista) en el bucle de uvicorn.

    Se llama desde código sync que puede correr en un hilo de worker, de ahí
    `run_coroutine_threadsafe` en vez de simplemente `await`.
    """
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(manager.broadcast_job(job_id), _loop)
    asyncio.run_coroutine_threadsafe(manager.broadcast_list(), _loop)


# ---------- contrato AgentCore ----------


@app.get("/ping")
def ping() -> dict:
    return {"status": "healthy"}


@app.post("/warmup")
def warmup() -> dict:
    """Paga por adelantado los costos de arranque en frío: carga el modelo de
    rembg en memoria y resuelve/prueba el proveedor de IA con una llamada real.

    Deliberadamente separado de `/ping` (que debe seguir respondiendo al
    instante para no fallar el health check de App Runner/ECS) — este es el
    endpoint que se invoca a mano una vez, antes de grabar una demo o de
    empezar a procesar jobs reales, para que el primer request de verdad no
    pague ese costo.
    """
    result: dict = {}

    t0 = time.monotonic()
    _get_rembg_session()
    result["rembg_seconds"] = round(time.monotonic() - t0, 2)

    t0 = time.monotonic()
    try:
        warmup_model()
        result["model_provider_seconds"] = round(time.monotonic() - t0, 2)
        result["model_provider_ready"] = True
    except Exception as exc:
        result["model_provider_seconds"] = round(time.monotonic() - t0, 2)
        result["model_provider_ready"] = False
        result["model_provider_error"] = str(exc)

    return result


class InvocationRequest(BaseModel):
    prompt: str | None = None
    input: dict | None = None


@app.post("/invocations")
def invocations(req: InvocationRequest) -> dict:
    """Entrypoint que espera AgentCore Runtime."""
    payload = req.input or {}
    images = payload.get("images", [])
    if not images:
        return {"result": "SnapFlick listo. Envía {'input': {'images': [...]}}"}
    job = Job(id=uuid.uuid4().hex[:12], total_images=len(images))
    run_job(job, images, payload.get("background"))
    _sync_job_to_storage(job)
    return {"result": job.model_dump(mode="json")}


# ---------- API propia del producto ----------


@app.post("/jobs", response_model=Job)
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    background: UploadFile | None = File(None),
    background_key: str | None = Form(None),
    background_keys: str | None = Form(None),
) -> Job:
    """`background`/`background_key` fijan el fondo por defecto del lote.

    `background_keys`, si se manda, es un JSON array del mismo largo que
    `files` con el `background_key` guardado que le corresponde a cada foto
    (o `null` para dejarla en el fondo por defecto) — así cada producto del
    lote puede llevar un fondo distinto en vez de forzar uno solo para todos.
    """
    if len(files) > settings.max_images_per_job:
        raise HTTPException(400, f"Máximo {settings.max_images_per_job} imágenes por job")

    per_file_keys: list[str | None] = []
    if background_keys:
        try:
            per_file_keys = json.loads(background_keys)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "background_keys debe ser un JSON array") from exc
        if len(per_file_keys) != len(files):
            raise HTTPException(400, "background_keys debe tener un elemento por cada archivo")

    job_id = uuid.uuid4().hex[:12]
    indir = DATA / upload_original_dir(job_id)
    indir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    per_image_backgrounds: dict[str, str | None] = {}
    for i, f in enumerate(files):
        dest = indir / (f.filename or f"{uuid.uuid4().hex}.jpg")
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        paths.append(str(dest))
        if per_file_keys and per_file_keys[i]:
            per_image_backgrounds[str(dest)] = _resolve_background_path(per_file_keys[i])

    bg_path: str | None = None
    if background is not None:
        bg_path = str(indir.parent / "background.jpg")
        with open(bg_path, "wb") as fh:
            shutil.copyfileobj(background.file, fh)
    elif background_key:
        bg_path = _resolve_background_path(background_key)
    else:
        # Sin elección explícita: cae al fondo marcado como "Por defecto"
        # (ver PUT /backgrounds/default), si hay uno.
        default_key = _get_default_background_key()
        if default_key:
            bg_path = _resolve_background_path(default_key)

    job = Job(id=job_id, total_images=len(paths), background_key=bg_path)
    JOBS[job_id] = job
    STORE.save(job)
    _notify_change(job_id)
    background_tasks.add_task(_process, job_id, paths, bg_path, per_image_backgrounds)
    return job_to_public_dict(job)


def _persist_and_notify(job: Job) -> None:
    STORE.save(job)
    _notify_change(job.id)


def _process(
    job_id: str,
    paths: list[str],
    bg: str | None,
    per_image_backgrounds: dict[str, str | None] | None = None,
) -> None:
    job = JOBS[job_id]
    try:
        run_job(
            job,
            paths,
            bg,
            on_update=_persist_and_notify,
            per_image_backgrounds=per_image_backgrounds,
        )
        _sync_job_to_storage(job)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.errors.append(str(exc))
    finally:
        STORE.save(job)
        _notify_change(job_id)


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    return job_to_public_dict(JOBS[job_id])


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Elimina un catálogo por completo: estado (STORE) y artefactos (fotos
    originales, recortes, imágenes compuestas, miniaturas, catalogo.html/json)
    bajo `uploads/<job_id>/` y `catalogs/<job_id>/`. No toca `backgrounds/`
    (son un pool compartido entre jobs).

    Bloqueado mientras el job está `pending`/`processing`: `_process` sigue
    corriendo en un hilo de `BackgroundTasks` con una referencia directa al
    mismo objeto `Job` (ver "Job mutation, not replacement" en CLAUDE.md), y
    seguiría llamando `STORE.save`/`_sync_job_to_storage` después de borrarlo
    acá, resucitando el registro y los archivos a medio borrar.
    """
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    if job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise HTTPException(400, "No se puede eliminar un lote que todavía se está procesando")

    del JOBS[job_id]
    STORE.delete(job_id)
    storage = get_storage()
    storage.delete_prefix(f"uploads/{job_id}/")
    storage.delete_prefix(f"{catalog_dir(job_id)}/")

    _notify_change(job_id)
    return {"id": job_id, "deleted": True}


class CatalogMetaUpdate(BaseModel):
    """Metadatos del catálogo editables desde la vista de catálogo publicado."""

    catalog_title: str | None = None
    catalog_summary: str | None = None


@app.patch("/jobs/{job_id}", response_model=Job)
def update_catalog_meta(job_id: str, payload: CatalogMetaUpdate) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    if not job.plan:
        raise HTTPException(400, "El catálogo todavía no tiene un plan generado")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job.plan, field, value)

    if job.catalog_html_path:
        out_dir = Path(job.catalog_html_path).parent
        job.catalog_html_path = render_catalog_html(job, str(out_dir / "catalogo.html"))
        export_catalog_json(job, str(out_dir / "catalogo.json"))
        _sync_job_to_storage(job)

    STORE.save(job)
    _notify_change(job_id)
    return job_to_public_dict(job)


class ProductUpdate(BaseModel):
    """Campos editables por el usuario en la vista de revisión.

    Todos opcionales: el frontend solo envía los campos que el usuario tocó.
    `confidence`, `ingredients` y `language_detected` no se exponen porque la
    revisión humana los vuelve irrelevantes: una vez que una persona confirma
    o corrige el dato, ya no hace falta que la ficha "confíe" en la extracción.

    `visible` no es un campo de `ProductSheet` (no es un dato extraído del
    empaque) sino de `ProductRecord` — se maneja aparte del resto antes de
    aplicar el resto de los campos sobre `record.sheet`.
    """

    name: str | None = None
    brand: str | None = None
    presentation: str | None = None
    description: str | None = None
    category: str | None = None
    keywords: list[str] | None = None
    barcode: str | None = None
    notes: str | None = None
    visible: bool | None = None


@app.patch("/jobs/{job_id}/products/{product_id}", response_model=Job)
def update_product(job_id: str, product_id: str, payload: ProductUpdate) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    record = next((p for p in job.products if p.id == product_id), None)
    if record is None:
        raise HTTPException(404, "Producto no encontrado")

    updates = payload.model_dump(exclude_unset=True)
    visible = updates.pop("visible", None)
    if visible is not None:
        record.visible = visible
    for field, value in updates.items():
        setattr(record.sheet, field, value)

    new_category = updates.get("category")
    if new_category and job.plan:
        if new_category not in job.plan.categories:
            job.plan.categories.append(new_category)
        for assignment in job.plan.assignments:
            if assignment.product_id == product_id:
                assignment.category = new_category

    if job.plan and job.catalog_html_path:
        out_dir = Path(job.catalog_html_path).parent
        job.catalog_html_path = render_catalog_html(job, str(out_dir / "catalogo.html"))
        export_catalog_json(job, str(out_dir / "catalogo.json"))
        _sync_job_to_storage(job)

    STORE.save(job)
    _notify_change(job_id)
    return job_to_public_dict(job)


@app.delete("/jobs/{job_id}/products/{product_id}", response_model=Job)
def delete_product(job_id: str, product_id: str) -> dict:
    """Borra un producto del catálogo (no solo lo oculta, ver `ProductUpdate.visible`).

    No borra los archivos de imagen en disco/S3 — solo saca el producto de
    `job.products` y de la asignación de categoría del plan. Igual que
    `update_product`, re-renderiza el catálogo publicado para que el borrado
    se refleje ahí también.
    """
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    record = next((p for p in job.products if p.id == product_id), None)
    if record is None:
        raise HTTPException(404, "Producto no encontrado")

    job.products.remove(record)
    if job.plan:
        job.plan.assignments = [a for a in job.plan.assignments if a.product_id != product_id]

    if job.plan and job.catalog_html_path:
        out_dir = Path(job.catalog_html_path).parent
        job.catalog_html_path = render_catalog_html(job, str(out_dir / "catalogo.html"))
        export_catalog_json(job, str(out_dir / "catalogo.json"))
        _sync_job_to_storage(job)

    STORE.save(job)
    _notify_change(job_id)
    return job_to_public_dict(job)


@app.post("/jobs/{job_id}/products", response_model=Job)
def add_product(
    job_id: str, file: UploadFile = File(...), background_key: str | None = Form(None)
) -> dict:
    """Agrega un producto a un catálogo ya generado, sin tener que rehacer el lote.

    `background_key` es opcional — si no se manda, cae de vuelta al fondo por
    defecto del job (`job.background_key`), igual que antes de soportar
    fondos por producto.

    Ruta síncrona (no `async def`): `add_product_to_job` hace rembg + una
    llamada real al modelo de IA (extracción + replanificación de categorías),
    varios segundos de trabajo bloqueante — FastAPI corre las rutas `def` en
    threadpool, así que esto no bloquea el loop de eventos como sí lo haría
    dentro de una `async def`.
    """
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    if job.status != JobStatus.DONE:
        raise HTTPException(400, "Solo se pueden agregar productos a un catálogo ya generado")

    indir = DATA / upload_original_dir(job_id)
    indir.mkdir(parents=True, exist_ok=True)
    dest = indir / (file.filename or f"{uuid.uuid4().hex}.jpg")
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    bg_path = _resolve_background_path(background_key) if background_key else job.background_key
    try:
        add_product_to_job(job, str(dest), bg_path)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc

    _sync_job_to_storage(job)
    STORE.save(job)
    _notify_change(job_id)
    return job_to_public_dict(job)


class ProductBackgroundUpdate(BaseModel):
    """`background_key` guardado (ver `GET /backgrounds`), o `None` para
    fondo blanco."""

    background_key: str | None = None


@app.patch("/jobs/{job_id}/products/{product_id}/background", response_model=Job)
def update_product_background(
    job_id: str, product_id: str, payload: ProductBackgroundUpdate
) -> dict:
    """Cambia el fondo de un producto ya procesado, recomponiendo su imagen.

    A diferencia de `update_product` (campos de la ficha extraída), esto solo
    toca la imagen — reutiliza el recorte (`image.cutout_path`) ya calculado
    por rembg, sin volver a llamar al modelo de IA.
    """
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]

    bg_path = _resolve_background_path(payload.background_key)
    try:
        recompose_product_background(job, product_id, bg_path)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc

    _sync_job_to_storage(job)
    STORE.save(job)
    _notify_change(job_id)
    return job_to_public_dict(job)


@app.get("/jobs")
def list_jobs() -> list[dict]:
    return _job_summaries()


@app.websocket("/ws/jobs")
async def ws_jobs(websocket: WebSocket) -> None:
    await manager.connect_list(websocket)
    try:
        while True:
            await websocket.receive_text()  # sin mensajes esperados; solo detecta el cierre
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_list(websocket)


@app.websocket("/ws/jobs/{job_id}")
async def ws_job(websocket: WebSocket, job_id: str) -> None:
    await manager.connect_job(websocket, job_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect_job(websocket, job_id)


@app.post("/backgrounds")
async def upload_background(file: UploadFile = File(...)) -> dict:
    """Guarda un fondo de marca reutilizable."""
    key = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    dest = DATA / background_key(key)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    if settings.s3_bucket:
        try:
            get_storage().save(str(dest), background_key(key))
        except Exception:
            log.exception("No se pudo subir el fondo %s a S3", key)
    return {"background_key": key, "url": _to_url(str(dest)), "is_default": False}


@app.get("/backgrounds")
def list_backgrounds() -> list[dict]:
    """Lista los fondos de marca guardados previamente.

    Va siempre a través de `Storage.list_keys` (disco local o S3, según
    `SNAPFLICK_S3_BUCKET`) en vez de leer el disco local directamente — así
    esto también funciona detrás de un despliegue con varias instancias.
    """
    storage = get_storage()
    default_key = _get_default_background_key()
    return [
        {
            "background_key": key.removeprefix("backgrounds/"),
            "url": storage.url(key),
            "is_default": key.removeprefix("backgrounds/") == default_key,
        }
        for key in storage.list_keys("backgrounds/")
        if key != _DEFAULT_BACKGROUND_STORAGE_KEY
    ]


class DefaultBackgroundUpdate(BaseModel):
    background_key: str | None = None


@app.put("/backgrounds/default")
def set_default_background(payload: DefaultBackgroundUpdate) -> dict:
    """Marca uno de los fondos guardados como el "Por defecto" del pool
    compartido (o lo desmarca con `background_key: null`).

    Un job nuevo sin fondo elegido explícitamente cae de vuelta a este fondo
    en vez de a blanco (ver `create_job`). No afecta jobs ya creados.
    """
    if payload.background_key:
        storage = get_storage()
        if not storage.exists(background_key(payload.background_key)):
            raise HTTPException(404, "Fondo no encontrado")
    _set_default_background_key(payload.background_key)
    return {"default_background_key": payload.background_key}
