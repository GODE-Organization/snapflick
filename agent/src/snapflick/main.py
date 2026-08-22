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
    return job


def _process(job_id: str, paths: list[str], bg: str | None) -> None:
    job = JOBS[job_id]
    try:
        run_job(job, paths, bg)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.errors.append(str(exc))


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    if job_id not in JOBS:
        raise HTTPException(404, "Job no encontrado")
    return JOBS[job_id]


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
