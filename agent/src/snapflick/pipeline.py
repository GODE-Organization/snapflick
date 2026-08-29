"""Orquestación del flujo completo. Un job entra, un catálogo sale."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from pathlib import Path

from .agents.catalog_agent import build_catalog_agent, plan_catalog
from .agents.vision_agent import build_vision_agent, extract_product_sheet
from .config import settings
from .models.schemas import Job, JobStatus, ProcessedImage, ProductRecord
from .tools.catalog_tools import export_catalog_json, render_catalog_html
from .tools.image_tools import compose_on_background, make_thumbnail, remove_background

log = logging.getLogger(__name__)

_GEMINI_STATUS_MESSAGES = {
    "UNAVAILABLE": (
        "El modelo de IA está temporalmente saturado por alta demanda. "
        "Vuelve a intentarlo en unos minutos."
    ),
    "RESOURCE_EXHAUSTED": (
        "Se alcanzó el límite de uso del modelo de IA. Intenta de nuevo más tarde."
    ),
    "DEADLINE_EXCEEDED": "El modelo de IA tardó demasiado en responder. Vuelve a intentarlo.",
    "UNAUTHENTICATED": (
        "Error de autenticación con el proveedor de IA. Verifica la API key configurada."
    ),
    "PERMISSION_DENIED": (
        "El proveedor de IA rechazó la solicitud por permisos. Verifica la API key configurada."
    ),
    "INVALID_ARGUMENT": "La foto no pudo ser interpretada por el modelo de IA.",
}

# Usado como fallback para proveedores cuyo SDK expone un status_code HTTP
# (OpenAI/ChatGPT, Ollama) en vez del string de status de Gemini.
_HTTP_CODE_MESSAGES = {
    401: "Error de autenticación con el proveedor de IA. Verifica la API key configurada.",
    403: "El proveedor de IA rechazó la solicitud por permisos. Verifica la API key configurada.",
    404: "El modelo de IA configurado no existe o no está disponible para esta cuenta.",
    408: "El modelo de IA tardó demasiado en responder. Vuelve a intentarlo.",
    429: "Se alcanzó el límite de uso del modelo de IA. Intenta de nuevo más tarde.",
    500: "El modelo de IA tuvo un error interno. Vuelve a intentarlo en unos minutos.",
    502: _GEMINI_STATUS_MESSAGES["UNAVAILABLE"],
    503: _GEMINI_STATUS_MESSAGES["UNAVAILABLE"],
    504: "El modelo de IA tardó demasiado en responder. Vuelve a intentarlo.",
}


def _friendly_error_message(exc: Exception) -> str:
    """Traduce errores de proveedores de IA (y otros) a un mensaje breve en
    español apto para mostrar en el front, en vez de la excepción cruda (que
    para GeminiModel/OpenAI incluye el JSON completo de la respuesta de error)."""
    try:
        from google.genai.errors import APIError as GeminiAPIError
    except ImportError:
        GeminiAPIError = ()  # type: ignore[assignment]

    if isinstance(exc, GeminiAPIError):
        status = exc.status or ""
        known = _GEMINI_STATUS_MESSAGES.get(status)
        if known:
            return known
        return f"Error del modelo de IA ({exc.code} {status}): {exc.message or 'sin detalle'}."

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        known = _HTTP_CODE_MESSAGES.get(status_code)
        if known:
            return known
        message = getattr(exc, "message", None) or str(exc)
        return f"Error del modelo de IA ({status_code}): {message}"

    if type(exc).__name__ in ("ConnectionError", "ConnectError"):
        return "No se pudo conectar con el modelo de IA. Verifica que el servicio esté disponible."

    return f"No se pudo procesar la imagen ({type(exc).__name__}): {exc}"


def run_job(
    job: Job,
    image_paths: list[str],
    background_path: str | None = None,
    workdir: Path | None = None,
    on_update: Callable[[Job], None] | None = None,
) -> Job:
    """Procesa `job` in place. El llamador es dueño del objeto `Job` (p.ej. el que
    vive en el diccionario JOBS de main.py), así que cualquiera que tenga una
    referencia ve `processed_images` avanzar mientras el lote corre.

    `on_update`, si se pasa, se llama después de cada imagen y al terminar el
    lote — main.py lo usa para persistir el progreso en SQLite a medida que
    avanza, no solo al final (ver `db.JobStore`)."""
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
            friendly = _friendly_error_message(exc)
            img.error = friendly
            job.errors.append(f"{Path(src).name}: {friendly}")
        finally:
            job.processed_images += 1
            if on_update:
                on_update(job)

    if not job.products:
        job.status = JobStatus.FAILED
        if on_update:
            on_update(job)
        return job

    job.plan = plan_catalog(job.products, agent=build_catalog_agent())
    for a in job.plan.assignments:
        for p in job.products:
            if p.id == a.product_id:
                p.sheet.category = a.category

    job.catalog_html_path = render_catalog_html(job, str(out / "catalogo.html"))
    job.catalog_json_path = export_catalog_json(job, str(out / "catalogo.json"))
    job.status = JobStatus.DONE
    if on_update:
        on_update(job)
    return job
