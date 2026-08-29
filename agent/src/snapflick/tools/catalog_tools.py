"""Renderizado del catálogo a HTML y JSON."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models.schemas import Job

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def _image_data_uri(path: str | None) -> str:
    """Incrusta la imagen como data: URI en base64.

    El HTML del catálogo está pensado para abrirse con doble clic (ver
    docs/03-revision-tecnica.md, hallazgo #2) — una ruta de archivo o relativa se rompe en
    cuanto el .html se mueve o se copia fuera de su carpeta de origen.
    """
    if not path or not Path(path).exists():
        return ""
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def render_catalog_html(job: Job, output_path: str, embed_images: bool = True) -> str:
    """Agrupa los productos visibles por categoría y escribe el catálogo HTML.

    Los productos con `visible=False` se ocultan del catálogo publicado (esta
    función) sin borrarlos del job — siguen viéndose en las vistas de
    administrador, que leen `job.products` directamente vía la API.
    """
    assert job.plan, "El job necesita un CatalogPlan antes de renderizar"
    visible = {p.id: p for p in job.products if p.visible}
    grouped: dict[str, list] = {c: [] for c in job.plan.categories}
    for a in job.plan.assignments:
        product = visible.get(a.product_id)
        if product is not None:
            grouped.setdefault(a.category, []).append(product)

    image_srcs = {}
    for p in visible.values():
        path = p.image.composed_path or p.image.source_path
        image_srcs[p.id] = _image_data_uri(path) if embed_images else path

    html = (
        _env()
        .get_template("catalog.html.j2")
        .render(
            title=job.plan.catalog_title,
            summary=job.plan.catalog_summary,
            grouped=grouped,
            total=len(visible),
            image_srcs=image_srcs,
        )
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def export_catalog_json(job: Job, output_path: str) -> str:
    """Exporta el job a JSON, igual que `render_catalog_html`, sin los productos ocultos."""
    data = job.model_dump(mode="json")
    data["products"] = [p for p in data["products"] if p["visible"]]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
