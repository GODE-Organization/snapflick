"""Orquestación del flujo completo. Un job entra, un catálogo sale."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from .agents.catalog_agent import build_catalog_agent, plan_catalog
from .agents.vision_agent import build_vision_agent, extract_product_sheet
from .config import settings
from .models.schemas import Job, JobStatus, ProcessedImage, ProductRecord
from .tools.catalog_tools import export_catalog_json, render_catalog_html
from .tools.image_tools import compose_on_background, make_thumbnail, remove_background

log = logging.getLogger(__name__)


def run_job(
    job: Job,
    image_paths: list[str],
    background_path: str | None = None,
    workdir: Path | None = None,
) -> Job:
    """Procesa `job` in place. El llamador es dueño del objeto `Job` (p.ej. el que
    vive en el diccionario JOBS de main.py), así que cualquiera que tenga una
    referencia ve `processed_images` avanzar mientras el lote corre."""
    job.status = JobStatus.PROCESSING
    out = Path(workdir or settings.data_dir) / job.id
    out.mkdir(parents=True, exist_ok=True)

    vision = build_vision_agent()

    for src in image_paths:
        stem = Path(src).stem
        img = ProcessedImage(source_path=src)
        try:
            img.cutout_path = remove_background(src, str(out / f"{stem}_cutout.png"))
            img.composed_path = compose_on_background(
                img.cutout_path, background_path, str(out / f"{stem}.jpg")
            )
            img.thumbnail_path = make_thumbnail(img.composed_path, str(out / f"{stem}_thumb.jpg"))
            sheet = extract_product_sheet(src, agent=vision)
            job.products.append(ProductRecord(id=uuid.uuid4().hex[:8], sheet=sheet, image=img))
        except Exception as exc:  # una imagen mala no puede tumbar el lote
            log.exception("Fallo procesando %s", src)
            img.error = str(exc)
            job.errors.append(f"{src}: {exc}")
        finally:
            job.processed_images += 1

    if not job.products:
        job.status = JobStatus.FAILED
        return job

    job.plan = plan_catalog(job.products, agent=build_catalog_agent())
    for a in job.plan.assignments:
        for p in job.products:
            if p.id == a.product_id:
                p.sheet.category = a.category

    job.catalog_html_path = render_catalog_html(job, str(out / "catalogo.html"))
    export_catalog_json(job, str(out / "catalogo.json"))
    job.status = JobStatus.DONE
    return job
