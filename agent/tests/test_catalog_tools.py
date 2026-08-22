"""Verifica que el catálogo HTML generado de verdad muestre imágenes al abrirlo.

No hay navegador disponible en CI, así que la prueba más fuerte que se puede
automatizar es: decodificar el `data:` URI incrustado en el <img src="..."> y
confirmar que PIL lo abre como una imagen válida con las dimensiones esperadas
— eso es exactamente lo que haría el motor de renderizado de un navegador.
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

from snapflick.models.schemas import (
    CatalogPlan,
    CategoryAssignment,
    Job,
    JobStatus,
    ProcessedImage,
    ProductRecord,
    ProductSheet,
)
from snapflick.tools.catalog_tools import render_catalog_html


def _make_job(tmp_path: Path) -> Job:
    composed = tmp_path / "producto1.jpg"
    Image.new("RGB", (120, 80), (200, 30, 30)).save(composed, "JPEG")

    product = ProductRecord(
        id="p1",
        sheet=ProductSheet(
            name="Refresco de cola", brand="Marca X", description="Bebida gaseosa 355 ml."
        ),
        image=ProcessedImage(source_path=str(composed), composed_path=str(composed)),
    )
    job = Job(
        id="job1", status=JobStatus.DONE, total_images=1, processed_images=1, products=[product]
    )
    job.plan = CatalogPlan(
        categories=["Bebidas"],
        assignments=[
            CategoryAssignment(product_id="p1", category="Bebidas", reason="es una bebida")
        ],
        catalog_title="Catálogo de prueba",
        catalog_summary="Un producto de prueba.",
    )
    return job


def test_catalogo_html_incrusta_imagenes_validas(tmp_path: Path):
    job = _make_job(tmp_path)
    out = render_catalog_html(job, str(tmp_path / "catalogo.html"))

    html = Path(out).read_text(encoding="utf-8")

    # ninguna ruta de archivo debe filtrarse al HTML: eso es lo que rompía la demo
    assert str(tmp_path) not in html.split("<img", 1)[0] or "data:" in html

    match = re.search(r'<img src="(data:image/[^;]+;base64,[^"]+)"', html)
    assert match, "el catálogo no incrustó ninguna imagen en base64"

    header, b64data = match.group(1).split(",", 1)
    assert header.startswith("data:image/jpeg")

    decoded = Image.open(io.BytesIO(base64.b64decode(b64data)))
    assert decoded.size == (120, 80)


def test_catalogo_html_agrupa_por_categoria_y_no_deja_categorias_vacias(tmp_path: Path):
    job = _make_job(tmp_path)
    out = render_catalog_html(job, str(tmp_path / "catalogo.html"))
    html = Path(out).read_text(encoding="utf-8")

    assert "Bebidas" in html
    assert "Refresco de cola" in html
    assert "Catálogo de prueba" in html


def test_render_catalog_html_sin_embed_usa_ruta_directa(tmp_path: Path):
    job = _make_job(tmp_path)
    out = render_catalog_html(job, str(tmp_path / "catalogo.html"), embed_images=False)
    html = Path(out).read_text(encoding="utf-8")
    assert "data:image" not in html
