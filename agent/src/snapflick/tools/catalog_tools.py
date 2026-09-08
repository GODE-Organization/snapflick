"""Renderizado del catálogo a HTML, JSON y PDF."""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models.schemas import Job, ProductRecord

log = logging.getLogger(__name__)

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


def _grouped_visible_products(job: Job) -> dict[str, list[ProductRecord]]:
    """Productos visibles agrupados por categoría, en el orden de `job.plan.categories`.

    Compartido por `render_catalog_html` y `render_catalog_pdf` para que ambos
    catálogos (el publicado y el PDF) siempre reflejen la misma vista.
    """
    assert job.plan, "El job necesita un CatalogPlan antes de renderizar"
    visible = {p.id: p for p in job.products if p.visible}
    grouped: dict[str, list[ProductRecord]] = {c: [] for c in job.plan.categories}
    for a in job.plan.assignments:
        product = visible.get(a.product_id)
        if product is not None:
            grouped.setdefault(a.category, []).append(product)
    return grouped


def render_catalog_html(job: Job, output_path: str, embed_images: bool = True) -> str:
    """Agrupa los productos visibles por categoría y escribe el catálogo HTML.

    Los productos con `visible=False` se ocultan del catálogo publicado (esta
    función) sin borrarlos del job — siguen viéndose en las vistas de
    administrador, que leen `job.products` directamente vía la API.
    """
    grouped = _grouped_visible_products(job)
    visible = {p.id: p for p in job.products if p.visible}

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


_PDF_MARGIN = 15  # mm
_PDF_IMAGE_SIZE = 42  # mm, imagen cuadrada por fila
_PDF_ROW_HEIGHT = 50  # mm, alto fijo por producto (ver nota abajo)
_PDF_DESCRIPTION_MAX_CHARS = 220  # trunca para que no se desborde de la fila fija

# Las fuentes "core" de fpdf2 (helvetica, times, courier) solo soportan Latin-1:
# cualquier caracter fuera de ese rango (comillas tipográficas, guiones largos,
# "…", viñetas, emoji) hace que fpdf2 tire FPDFUnicodeEncodingException. Las
# fichas de producto salen de un modelo de IA, que genera justo ese tipo de
# puntuación con frecuencia — no es un caso hipotético, reventó en la primera
# prueba con texto de ejemplo. Mapear los casos comunes a su equivalente ASCII
# y, como red de seguridad, descartar silenciosamente cualquier otro caracter
# no soportado en vez de sumar una fuente TTF completa solo para esto.
_PDF_CHAR_REPLACEMENTS = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "•": "-",
}


def _pdf_safe_text(text: str) -> str:
    for char, replacement in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def render_catalog_pdf(job: Job, output_path: str) -> str:
    """Genera un PDF plano del catálogo: portada + una fila por producto visible
    (imagen + marca/nombre/presentación/descripción), agrupados por categoría
    igual que `render_catalog_html`.

    Deliberadamente no es un renderizador HTML-a-PDF (weasyprint/wkhtmltopdf):
    esas herramientas dependen de librerías nativas (Cairo/Pango o un motor
    WebKit embebido), el mismo tipo de riesgo de build multi-arch que ya afecta
    a onnxruntime bajo QEMU (ver Gotchas en CLAUDE.md). `fpdf2` es puro Python
    y solo dibuja texto e imágenes sobre un canvas, así que no lo repite.

    El alto de fila es fijo (`_PDF_ROW_HEIGHT`) en vez de medido dinámicamente
    porque fpdf2 no expone una forma barata de medir el alto de un `multi_cell`
    antes de dibujarlo — se trunca la descripción para que quepa. Suficiente
    para una primera versión "catálogo con fotos"; si hace falta más fidelidad
    después, ahí se justifica medir el texto o pasar a un layout dinámico.
    """
    grouped = _grouped_visible_products(job)
    total = sum(len(products) for products in grouped.values())

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN)
    pdf.set_margins(_PDF_MARGIN, _PDF_MARGIN, _PDF_MARGIN)
    page_width = pdf.w - 2 * _PDF_MARGIN

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(
        page_width, 10, _pdf_safe_text(job.plan.catalog_title), new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    if job.plan.catalog_summary:
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(
            page_width,
            7,
            _pdf_safe_text(job.plan.catalog_summary),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    plural_p = "s" if total != 1 else ""
    plural_c = "s" if len(grouped) != 1 else ""
    pdf.cell(
        page_width,
        8,
        f"{total} producto{plural_p} - {len(grouped)} categoria{plural_c}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    for category, products in grouped.items():
        if not products:
            continue
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(page_width, 10, _pdf_safe_text(category), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

        for product in products:
            if pdf.get_y() + _PDF_ROW_HEIGHT > pdf.h - _PDF_MARGIN:
                pdf.add_page()
            row_top = pdf.get_y()
            sheet = product.sheet
            image_path = product.image.composed_path or product.image.source_path
            if image_path and Path(image_path).exists():
                try:
                    pdf.image(
                        image_path, x=_PDF_MARGIN, y=row_top, w=_PDF_IMAGE_SIZE, h=_PDF_IMAGE_SIZE
                    )
                except Exception:
                    # A diferencia del HTML (que incrusta los bytes crudos sin
                    # decodificarlos), fpdf2 sí abre la imagen con Pillow acá —
                    # un archivo corrupto no debe tumbar todo el catálogo, solo
                    # dejar ese producto sin foto en el PDF.
                    log.warning("No se pudo incrustar la imagen %s en el PDF", image_path)

            text_x = _PDF_MARGIN + _PDF_IMAGE_SIZE + 6
            text_width = page_width - _PDF_IMAGE_SIZE - 6
            pdf.set_xy(text_x, row_top)

            if sheet.brand:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(110, 110, 110)
                pdf.cell(
                    text_width,
                    5,
                    _pdf_safe_text(sheet.brand.upper()),
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )
                pdf.set_x(text_x)

            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(
                text_width, 6, _pdf_safe_text(sheet.name), new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            pdf.set_x(text_x)

            if sheet.presentation:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(110, 110, 110)
                pdf.cell(
                    text_width,
                    5,
                    _pdf_safe_text(sheet.presentation),
                    new_x=XPos.LMARGIN,
                    new_y=YPos.NEXT,
                )
                pdf.set_x(text_x)

            description = sheet.description
            if len(description) > _PDF_DESCRIPTION_MAX_CHARS:
                description = description[: _PDF_DESCRIPTION_MAX_CHARS - 1].rstrip() + "..."
            pdf.set_text_color(60, 60, 60)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(text_width, 4.5, _pdf_safe_text(description))

            pdf.set_xy(_PDF_MARGIN, row_top + _PDF_ROW_HEIGHT)
            pdf.set_text_color(0, 0, 0)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    return output_path
