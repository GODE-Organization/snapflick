"""Renderizado del catálogo a HTML, JSON y PDF."""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path

from fpdf import FPDF
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
_PDF_CARD_GUTTER = 6  # mm, espacio entre las dos columnas de tarjetas
_PDF_CARD_IMAGE_H = 52  # mm, alto del recuadro de imagen dentro de la tarjeta
_PDF_CARD_PADDING = 5  # mm, relleno interno de la tarjeta
_PDF_DESCRIPTION_MAX_LINES = 4
_PDF_NAME_MAX_LINES = 2

# Paleta tomada de templates/catalog.html.j2 (design system "Lumina AI") para
# que el PDF descargable se sienta como la misma marca que el catálogo web,
# no como un documento aparte generado por otra herramienta.
_PDF_PRIMARY = (70, 72, 212)  # #4648D4
_PDF_ACCENT = (99, 102, 241)  # #6366F1
_PDF_CYAN = (34, 211, 238)  # #22D3EE
_PDF_INK = (23, 28, 33)  # #171C21
_PDF_INK_MUTED = (70, 69, 84)  # #464554
_PDF_SURFACE_MUTED = (234, 238, 245)  # #EAEEF5
_PDF_SURFACE_VARIANT = (222, 227, 233)  # #DEE3E9
_PDF_WARN = (138, 109, 0)  # #8A6D00
_PDF_WARN_BG = (255, 246, 214)  # #FFF6D6
_PDF_WHITE = (255, 255, 255)

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


class _CatalogPDF(FPDF):
    """`FPDF` con encabezado/pie de página compartidos por todas las páginas de
    categoría, para no repetir esa lógica en cada `add_page()`. La portada
    (página 1) se salta ambos: lleva su propio bloque de color a medida."""

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_fill_color(*_PDF_PRIMARY)
        self.rect(0, 0, self.w, 2.5, style="F")

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-16)
        self.set_draw_color(*_PDF_SURFACE_VARIANT)
        self.line(_PDF_MARGIN, self.get_y(), self.w - _PDF_MARGIN, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_PDF_INK_MUTED)
        self.set_xy(_PDF_MARGIN, self.get_y() + 3)
        self.cell(self.w - 2 * _PDF_MARGIN - 30, 6, "SnapFlick - Catalogo generado con IA")
        self.set_xy(self.w - _PDF_MARGIN - 30, self.get_y())
        self.cell(30, 6, f"Pagina {self.page_no()} de {{nb}}", align="R")


def _pdf_wrap_lines(pdf: FPDF, text: str, width: float, max_lines: int | None = None) -> list[str]:
    """Envuelve `text` al ancho dado usando el motor de layout de fpdf2 (sin
    dibujar nada) y, si excede `max_lines`, recorta con "..." — reemplaza el
    truncado por caracteres fijo de la versión anterior, que no tenía en
    cuenta el ancho real de fuente.

    Sanea con `_pdf_safe_text` antes de medir: fpdf2 mide con el mismo motor
    de fuentes Latin-1 con el que luego dibuja, así que un caracter fuera de
    rango revienta aquí igual que en `multi_cell`/`cell` reales.
    """
    lines = pdf.multi_cell(width, 0, _pdf_safe_text(text), dry_run=True, output="LINES")
    if max_lines and len(lines) > max_lines:
        kept = lines[:max_lines]
        last = kept[-1]
        while pdf.get_string_width(last + "...") > width and len(last) > 1:
            last = last[:-1].rstrip()
        kept[-1] = last.rstrip() + "..."
        lines = kept
    return lines


def _pdf_pill(
    pdf: FPDF,
    x: float,
    y: float,
    text: str,
    fill_rgb: tuple[int, int, int],
    text_rgb: tuple[int, int, int],
    font_size: float = 8,
    height: float = 6.0,
    bold: bool = False,
) -> float:
    """Dibuja una píldora (rectángulo redondeado + texto centrado) y devuelve
    su ancho, para poder encadenar varias en fila (chips de tag/keyword)."""
    pdf.set_font("Helvetica", "B" if bold else "", font_size)
    text = _pdf_safe_text(text)
    width = pdf.get_string_width(text) + 6.0
    pdf.set_fill_color(*fill_rgb)
    pdf.rect(x, y, width, height, style="F", round_corners=True, corner_radius=height / 2)
    pdf.set_text_color(*text_rgb)
    pdf.set_xy(x, y)
    pdf.cell(width, height, text, align="C")
    return width


def _pdf_card_height(pdf: FPDF, product: ProductRecord, card_width: float) -> float:
    """Calcula el alto total que ocupará la tarjeta de `product`, sumando cada
    bloque de texto medido con `_pdf_wrap_lines` en vez de asumir un alto de
    fila fijo — así una descripción corta no deja un hueco enorme y una larga
    no se desborda de la tarjeta."""
    sheet = product.sheet
    text_w = card_width - 2 * _PDF_CARD_PADDING
    height = _PDF_CARD_PADDING + _PDF_CARD_IMAGE_H + 4

    if sheet.brand:
        height += 5
    name_lines = _pdf_wrap_lines(pdf, sheet.name, text_w, max_lines=_PDF_NAME_MAX_LINES)
    height += len(name_lines) * 5.2 + 2
    if sheet.presentation or sheet.category:
        height += 8
    desc_lines = _pdf_wrap_lines(
        pdf, sheet.description, text_w, max_lines=_PDF_DESCRIPTION_MAX_LINES
    )
    height += len(desc_lines) * 4.3 + 2
    if sheet.keywords:
        height += 7
    height += _PDF_CARD_PADDING
    return height


def _pdf_draw_card(
    pdf: FPDF, x: float, y: float, card_width: float, card_height: float, product: ProductRecord
) -> None:
    """Dibuja una tarjeta de producto completa (fondo, imagen, marca, nombre,
    tags, descripción, keywords) — el equivalente en PDF de `.card` en
    `catalog.html.j2`."""
    sheet = product.sheet
    pad = _PDF_CARD_PADDING
    text_w = card_width - 2 * pad
    inner_x = x + pad

    pdf.set_draw_color(*_PDF_SURFACE_VARIANT)
    pdf.set_fill_color(*_PDF_WHITE)
    pdf.rect(x, y, card_width, card_height, style="DF", round_corners=True, corner_radius=3)

    image_top = y + pad
    pdf.set_fill_color(*_PDF_SURFACE_MUTED)
    pdf.rect(
        inner_x,
        image_top,
        text_w,
        _PDF_CARD_IMAGE_H,
        style="F",
        round_corners=True,
        corner_radius=2.5,
    )
    image_path = product.image.composed_path or product.image.source_path
    if image_path and Path(image_path).exists():
        try:
            pdf.image(
                image_path,
                x=inner_x,
                y=image_top,
                w=text_w,
                h=_PDF_CARD_IMAGE_H,
                keep_aspect_ratio=True,
            )
        except Exception:
            # A diferencia del HTML (que incrusta los bytes crudos sin
            # decodificarlos), fpdf2 sí abre la imagen con Pillow acá — un
            # archivo corrupto no debe tumbar todo el catálogo, solo dejar
            # ese producto sin foto en el PDF.
            log.warning("No se pudo incrustar la imagen %s en el PDF", image_path)
    if sheet.confidence == "low":
        _pdf_pill(
            pdf,
            inner_x + 2,
            image_top + 2,
            "REVISAR DATOS",
            _PDF_WARN_BG,
            _PDF_WARN,
            font_size=6.5,
            height=5,
            bold=True,
        )

    cursor_y = image_top + _PDF_CARD_IMAGE_H + 4

    if sheet.brand:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_PDF_INK_MUTED)
        pdf.set_xy(inner_x, cursor_y)
        pdf.cell(text_w, 4, _pdf_safe_text(sheet.brand.upper()))
        cursor_y += 5

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_PDF_INK)
    for line in _pdf_wrap_lines(pdf, sheet.name, text_w, max_lines=_PDF_NAME_MAX_LINES):
        pdf.set_xy(inner_x, cursor_y)
        pdf.cell(text_w, 5.2, _pdf_safe_text(line))
        cursor_y += 5.2
    cursor_y += 2

    if sheet.presentation or sheet.category:
        tag_x = inner_x
        if sheet.category:
            tag_x += (
                _pdf_pill(
                    pdf,
                    tag_x,
                    cursor_y,
                    sheet.category,
                    _PDF_ACCENT_SOFT,
                    _PDF_PRIMARY,
                    font_size=7.5,
                )
                + 3
            )
        if sheet.presentation:
            _pdf_pill(
                pdf,
                tag_x,
                cursor_y,
                sheet.presentation,
                _PDF_SURFACE_MUTED,
                _PDF_INK_MUTED,
                font_size=7.5,
            )
        cursor_y += 8

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_PDF_INK_MUTED)
    for line in _pdf_wrap_lines(
        pdf, sheet.description, text_w, max_lines=_PDF_DESCRIPTION_MAX_LINES
    ):
        pdf.set_xy(inner_x, cursor_y)
        pdf.cell(text_w, 4.3, _pdf_safe_text(line))
        cursor_y += 4.3
    cursor_y += 2

    if sheet.keywords:
        kw_x = inner_x
        for kw in sheet.keywords[:3]:
            kw_w = _pdf_pill(
                pdf, kw_x, cursor_y, kw, _PDF_SURFACE_MUTED, _PDF_INK_MUTED, font_size=7
            )
            kw_x += kw_w + 2
            if kw_x - inner_x > text_w:
                break

    pdf.set_text_color(*_PDF_INK)


_PDF_ACCENT_SOFT = (233, 233, 253)  # aproximación sólida de --accent-soft (rgba con alpha .1)


def render_catalog_pdf(job: Job, output_path: str) -> str:
    """Genera el catálogo en PDF: portada de marca + una cuadrícula de dos
    columnas de tarjetas de producto por categoría, agrupados igual que
    `render_catalog_html` y con la misma paleta que `catalog.html.j2`.

    Deliberadamente no es un renderizador HTML-a-PDF (weasyprint/wkhtmltopdf):
    esas herramientas dependen de librerías nativas (Cairo/Pango o un motor
    WebKit embebido), el mismo tipo de riesgo de build multi-arch que ya afecta
    a onnxruntime bajo QEMU (ver Gotchas en CLAUDE.md). `fpdf2` es puro Python
    y solo dibuja texto e imágenes sobre un canvas, así que no lo repite.

    El alto de cada tarjeta se mide con `_pdf_card_height` (usando el modo
    `dry_run` de `multi_cell` para envolver texto sin dibujarlo) en vez de
    asumir una fila fija: una descripción corta ya no deja un hueco enorme y
    una larga no se desborda ni se trunca a un número de caracteres arbitrario.
    """
    grouped = _grouped_visible_products(job)
    total = sum(len(products) for products in grouped.values())

    pdf = _CatalogPDF(unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=_PDF_MARGIN + 12)
    pdf.set_margins(_PDF_MARGIN, _PDF_MARGIN, _PDF_MARGIN)
    page_width = pdf.w - 2 * _PDF_MARGIN

    # --- Portada ---------------------------------------------------------
    pdf.add_page()
    cover_h = 78.0
    band_steps = 40
    for i in range(band_steps):
        t = i / (band_steps - 1)
        r = round(_PDF_PRIMARY[0] + (_PDF_CYAN[0] - _PDF_PRIMARY[0]) * t)
        g = round(_PDF_PRIMARY[1] + (_PDF_CYAN[1] - _PDF_PRIMARY[1]) * t)
        b = round(_PDF_PRIMARY[2] + (_PDF_CYAN[2] - _PDF_PRIMARY[2]) * t)
        pdf.set_fill_color(r, g, b)
        pdf.rect(0, cover_h * i / band_steps, pdf.w, cover_h / band_steps + 0.5, style="F")

    pdf.set_xy(_PDF_MARGIN, 14)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_PDF_WHITE)
    pdf.cell(page_width, 6, "SNAPFLICK")
    pdf.set_xy(_PDF_MARGIN, 30)
    pdf.set_font("Helvetica", "B", 26)
    for line in _pdf_wrap_lines(pdf, job.plan.catalog_title, page_width, max_lines=2):
        pdf.set_x(_PDF_MARGIN)
        pdf.cell(page_width, 11, _pdf_safe_text(line))
        pdf.ln(11)
    if job.plan.catalog_summary:
        pdf.set_font("Helvetica", "", 11.5)
        pdf.set_text_color(235, 236, 255)
        for line in _pdf_wrap_lines(pdf, job.plan.catalog_summary, page_width - 10, max_lines=2):
            pdf.set_x(_PDF_MARGIN)
            pdf.cell(page_width, 6, _pdf_safe_text(line))
            pdf.ln(6)

    pdf.set_text_color(*_PDF_INK)
    stats_y = cover_h + 12
    plural_p = "s" if total != 1 else ""
    plural_c = "s" if len(grouped) != 1 else ""
    pill_x = _PDF_MARGIN
    pill_x += (
        _pdf_pill(
            pdf,
            pill_x,
            stats_y,
            f"{total} PRODUCTO{plural_p.upper()}",
            _PDF_SURFACE_MUTED,
            _PDF_PRIMARY,
            font_size=9,
            height=8,
            bold=True,
        )
        + 4
    )
    _pdf_pill(
        pdf,
        pill_x,
        stats_y,
        f"{len(grouped)} CATEGORIA{plural_c.upper()}",
        _PDF_SURFACE_MUTED,
        _PDF_PRIMARY,
        font_size=9,
        height=8,
        bold=True,
    )

    cat_y = stats_y + 16
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_PDF_INK_MUTED)
    pdf.set_xy(_PDF_MARGIN, cat_y)
    pdf.cell(page_width, 5, "CATEGORIAS EN ESTE CATALOGO")
    cat_y += 8
    chip_x = _PDF_MARGIN
    for category, products in grouped.items():
        if not products:
            continue
        chip_w = _pdf_pill(
            pdf,
            chip_x,
            cat_y,
            f"{category} ({len(products)})",
            _PDF_WHITE,
            _PDF_INK_MUTED,
            font_size=8.5,
        )
        pdf.set_draw_color(*_PDF_SURFACE_VARIANT)
        pdf.rect(chip_x, cat_y, chip_w, 6, style="D", round_corners=True, corner_radius=3)
        chip_x += chip_w + 3
        if chip_x > pdf.w - _PDF_MARGIN - 25:
            chip_x = _PDF_MARGIN
            cat_y += 9

    # --- Categorías --------------------------------------------------------
    col_gutter = _PDF_CARD_GUTTER
    col_w = (page_width - col_gutter) / 2

    for category, products in grouped.items():
        if not products:
            continue
        pdf.add_page()
        pdf.set_fill_color(*_PDF_PRIMARY)
        pdf.rect(0, 0, pdf.w, 24, style="F")
        pdf.set_xy(_PDF_MARGIN, 8)
        pdf.set_font("Helvetica", "B", 15)
        pdf.set_text_color(*_PDF_WHITE)
        plural = "s" if len(products) != 1 else ""
        pdf.cell(page_width, 8, f"{_pdf_safe_text(category)}  -  {len(products)} producto{plural}")
        pdf.set_text_color(*_PDF_INK)
        pdf.set_y(24 + 8)

        row: list[ProductRecord] = []
        for product in products + [None]:  # type: ignore[list-item]
            if product is not None:
                row.append(product)
                if len(row) < 2:
                    continue
            if not row:
                continue

            heights = [_pdf_card_height(pdf, p, col_w) for p in row]
            row_h = max(heights)
            if pdf.get_y() + row_h > pdf.h - _PDF_MARGIN - 12:
                pdf.add_page()
                pdf.set_y(_PDF_MARGIN)
            row_top = pdf.get_y()
            for i, p in enumerate(row):
                card_x = _PDF_MARGIN + i * (col_w + col_gutter)
                _pdf_draw_card(pdf, card_x, row_top, col_w, row_h, p)
            pdf.set_y(row_top + row_h + col_gutter)
            row = []

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    return output_path
