"""API FastAPI. Cumple el contrato de AgentCore: /invocations y /ping en :8080."""

from __future__ import annotations

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

app = FastAPI(title="SnapFlick", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA = Path(settings.data_dir)
DATA.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(DATA)), name="files")

JOBS: dict[str, Job] = {}  # en producción: DynamoDB


def _to_url(path: str | None) -> str | None:
    """Convierte un path absoluto de filesystem (bajo DATA) en una URL /files/...

    Los paths que guarda `Job` son absolutos porque `pipeline.py` los usa para
    abrir archivos con Pillow. El frontend no conoce `SNAPFLICK_DATA_DIR` del
    servidor, así que esta capa HTTP es la única que traduce uno al otro.
    """
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(DATA.resolve())
    except ValueError:
        return None
    return f"/files/{rel.as_posix()}"


def job_to_public_dict(job: Job) -> dict:
    data = job.model_dump(mode="json")
    data["background_key"] = _to_url(job.background_key)
    data["catalog_html_path"] = _to_url(job.catalog_html_path)
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
    return {"background_key": key, "url": f"/files/backgrounds/{key}"}


@app.get("/backgrounds")
def list_backgrounds() -> list[dict]:
    """Lista los fondos de marca guardados previamente."""
    bg_dir = DATA / "backgrounds"
    if not bg_dir.exists():
        return []
    return [
        {"background_key": f.name, "url": f"/files/backgrounds/{f.name}"}
        for f in sorted(bg_dir.iterdir())
        if f.is_file()
    ]
