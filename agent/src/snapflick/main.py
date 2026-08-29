"""API FastAPI. Cumple el contrato de AgentCore: /invocations y /ping en :8080."""

from __future__ import annotations

import asyncio
import logging
import shutil
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
from .db import JobStore
from .models.schemas import Job, JobStatus
from .pipeline import run_job
from .tools.catalog_tools import export_catalog_json, render_catalog_html
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

STORE = JobStore(DATA / "snapflick.db")
JOBS: dict[str, Job] = {j.id: j for j in STORE.all()}  # caché en memoria; SQLite es la fuente


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
    data["background_key"] = _to_url(job.background_key)
    data["catalog_html_path"] = _to_url(job.catalog_html_path)
    data["catalog_json_path"] = _to_url(job.catalog_json_path)
    for product, record in zip(data["products"], job.products, strict=True):
        img = product["image"]
        img["source_path"] = _to_url(record.image.source_path)
        img["cutout_path"] = _to_url(record.image.cutout_path)
        img["composed_path"] = _to_url(record.image.composed_path)
        img["thumbnail_path"] = _to_url(record.image.thumbnail_path)
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
) -> Job:
    if len(files) > settings.max_images_per_job:
        raise HTTPException(400, f"Máximo {settings.max_images_per_job} imágenes por job")

    job_id = uuid.uuid4().hex[:12]
    indir = DATA / job_id / "original"
    indir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    for f in files:
        dest = indir / (f.filename or f"{uuid.uuid4().hex}.jpg")
        with dest.open("wb") as fh:
            shutil.copyfileobj(f.file, fh)
        paths.append(str(dest))

    bg_path: str | None = None
    if background is not None:
        bg_path = str(indir.parent / "background.jpg")
        with open(bg_path, "wb") as fh:
            shutil.copyfileobj(background.file, fh)
    elif background_key:
        bg_path = str(DATA / "backgrounds" / background_key)

    job = Job(id=job_id, total_images=len(paths), background_key=bg_path)
    JOBS[job_id] = job
    STORE.save(job)
    _notify_change(job_id)
    background_tasks.add_task(_process, job_id, paths, bg_path)
    return job_to_public_dict(job)


def _persist_and_notify(job: Job) -> None:
    STORE.save(job)
    _notify_change(job.id)


def _process(job_id: str, paths: list[str], bg: str | None) -> None:
    job = JOBS[job_id]
    try:
        run_job(job, paths, bg, on_update=_persist_and_notify)
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


class ProductSheetUpdate(BaseModel):
    """Campos editables por el usuario en la vista de revisión.

    Todos opcionales: el frontend solo envía los campos que el usuario tocó.
    `confidence`, `ingredients` y `language_detected` no se exponen porque la
    revisión humana los vuelve irrelevantes: una vez que una persona confirma
    o corrige el dato, ya no hace falta que la ficha "confíe" en la extracción.
    """

    name: str | None = None
    brand: str | None = None
    presentation: str | None = None
    description: str | None = None
    category: str | None = None
    keywords: list[str] | None = None
    barcode: str | None = None
    notes: str | None = None


@app.patch("/jobs/{job_id}/products/{product_id}", response_model=Job)
def update_product(job_id: str, product_id: str, payload: ProductSheetUpdate) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    job = JOBS[job_id]
    record = next((p for p in job.products if p.id == product_id), None)
    if record is None:
        raise HTTPException(404, "Producto no encontrado")

    updates = payload.model_dump(exclude_unset=True)
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
    dest = DATA / "backgrounds" / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    if settings.s3_bucket:
        try:
            get_storage().save(str(dest), f"backgrounds/{key}")
        except Exception:
            log.exception("No se pudo subir el fondo %s a S3", key)
    return {"background_key": key, "url": _to_url(str(dest))}


@app.get("/backgrounds")
def list_backgrounds() -> list[dict]:
    """Lista los fondos de marca guardados previamente."""
    bg_dir = DATA / "backgrounds"
    if not bg_dir.exists():
        return []
    return [
        {"background_key": f.name, "url": _to_url(str(f))}
        for f in sorted(bg_dir.iterdir())
        if f.is_file()
    ]
