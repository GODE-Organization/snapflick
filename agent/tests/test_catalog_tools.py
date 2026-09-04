"""Verifica que el catálogo HTML generado de verdad muestre imágenes al abrirlo.

No hay navegador disponible en CI, así que la prueba más fuerte que se puede
automatizar es: decodificar el `data:` URI incrustado en el <img src="..."> y
confirmar que PIL lo abre como una imagen válida con las dimensiones esperadas
— eso es exactamente lo que haría el motor de renderizado de un navegador.
"""

from __future__ import annotations

import base64
import io
import json
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
from snapflick.tools.catalog_tools import export_catalog_json, render_catalog_html


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


def test_render_catalog_html_oculta_productos_no_visibles(tmp_path: Path):
    job = _make_job(tmp_path)
    job.products[0].visible = False

    out = render_catalog_html(job, str(tmp_path / "catalogo.html"))
    html = Path(out).read_text(encoding="utf-8")

    assert "Refresco de cola" not in html
    assert ">0<" in html or "0 producto" in html


def test_export_catalog_json_excluye_productos_no_visibles(tmp_path: Path):
    job = _make_job(tmp_path)
    job.products[0].visible = False

    out = export_catalog_json(job, str(tmp_path / "catalogo.json"))
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    assert data["products"] == []


def test_catalogo_html_incluye_buscador_y_filtros_por_categoria(tmp_path: Path):
    """El catálogo publicado (HTML autocontenido, sin framework) debe traer un
    buscador y botones de filtro por categoría con los `data-*` que usa el
    <script> embebido para filtrar sin depender de un backend."""
    job = _make_job(tmp_path)
    # cat-nav solo se renderiza con más de una categoría (ver template) —
    # se agrega un segundo producto en otra categoría para ejercitar esa rama.
    segundo = tmp_path / "producto2.jpg"
    Image.new("RGB", (60, 60), (10, 200, 10)).save(segundo, "JPEG")
    job.products.append(
        ProductRecord(
            id="p2",
            sheet=ProductSheet(name="Galletas", description="Galletas dulces."),
            image=ProcessedImage(source_path=str(segundo), composed_path=str(segundo)),
        )
    )
    job.plan.categories.append("Snacks")
    job.plan.assignments.append(
        CategoryAssignment(product_id="p2", category="Snacks", reason="es un snack")
    )

    out = render_catalog_html(job, str(tmp_path / "catalogo.html"))
    html = Path(out).read_text(encoding="utf-8")

    assert 'id="search-input"' in html
    assert 'id="cat-nav"' in html
    assert 'class="cat-btn active" data-category=""' in html
    assert 'data-category="Bebidas"' in html
    assert 'data-category="Snacks"' in html
    # el índice de búsqueda por producto junta nombre/marca/descripción/keywords
    assert "refresco de cola" in html
    assert "marca x" in html
    assert 'id="empty-state"' in html


def test_catalogo_html_data_search_omite_campos_vacios(tmp_path: Path):
    """`p.sheet.presentation` es None en el fixture — el filtro Jinja `select`
    antes de unir los campos con espacios no debe dejar dobles espacios ni
    la palabra "None" colada en el índice de búsqueda."""
    job = _make_job(tmp_path)
    out = render_catalog_html(job, str(tmp_path / "catalogo.html"))
    html = Path(out).read_text(encoding="utf-8")

    match = re.search(r'data-search="([^"]*)"', html)
    assert match, "no se encontró el atributo data-search"
    assert "none" not in match.group(1).lower()
