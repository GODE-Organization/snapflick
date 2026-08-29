"""API FastAPI. Cumple el contrato de AgentCore: /invocations y /ping en :8080."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .models.schemas import Job, JobStatus
from .pipeline import run_job
from .tools.storage_tools import get_storage

log = logging.getLogger(__name__)

app = FastAPI(title="SnapFlick", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA = Path(settings.data_dir)
DATA.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(DATA)), name="files")

JOBS: dict[str, Job] = {}  # en producción: DynamoDB


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
    background_tasks.add_task(_process, job_id, paths, bg_path)
    return job_to_public_dict(job)


def _process(job_id: str, paths: list[str], bg: str | None) -> None:
    job = JOBS[job_id]
    try:
        run_job(job, paths, bg)
        _sync_job_to_storage(job)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.errors.append(str(exc))


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> dict:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    return job_to_public_dict(JOBS[job_id])


@app.get("/jobs")
def list_jobs() -> list[dict]:
    return [
        {"id": j.id, "status": j.status, "products": len(j.products), "created_at": j.created_at}
        for j in JOBS.values()
    ]


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
