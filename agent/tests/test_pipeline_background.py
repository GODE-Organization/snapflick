"""Cambiar el fondo de un producto ya extraído es pura composición de imagen
(Pillow), sin rembg ni modelo de IA — estas pruebas corren con imágenes reales
y no necesitan mockear nada."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import snapflick.pipeline as pipeline_module
from snapflick.models.schemas import (
    CatalogPlan,
    CategoryAssignment,
    Job,
    JobStatus,
    ProcessedImage,
    ProductRecord,
    ProductSheet,
)
from snapflick.pipeline import KEEP_ORIGINAL_BACKGROUND, recompose_product_background


def _make_job_with_cutout(tmp_path: Path) -> Job:
    cutout = tmp_path / "producto_cutout.png"
    Image.new("RGBA", (100, 100), (0, 200, 0, 255)).save(cutout, "PNG")

    product = ProductRecord(
        id="p1",
        sheet=ProductSheet(name="Producto", description="Descripción de prueba."),
        image=ProcessedImage(
            source_path=str(tmp_path / "producto.jpg"),
            cutout_path=str(cutout),
        ),
    )
    job = Job(
        id="job-bg", status=JobStatus.DONE, total_images=1, processed_images=1, products=[product]
    )
    job.plan = CatalogPlan(
        categories=["Otros"],
        assignments=[CategoryAssignment(product_id="p1", category="Otros", reason="prueba")],
        catalog_title="Catálogo",
        catalog_summary="Resumen",
    )
    return job


def test_recompose_cambia_el_fondo_y_actualiza_el_record(tmp_path):
    job = _make_job_with_cutout(tmp_path)
    background = tmp_path / "fondo.jpg"
    Image.new("RGB", (300, 300), (10, 20, 30)).save(background, "JPEG")

    record = recompose_product_background(job, "p1", str(background), workdir=tmp_path)

    assert record.background_key == str(background)
    assert record.image.composed_path is not None
    composed = Image.open(record.image.composed_path)
    assert composed.mode == "RGB"
    # esquina de la imagen compuesta = color del fondo (el producto está centrado)
    assert composed.getpixel((0, 0)) == (10, 20, 30)
    assert record.image.thumbnail_path is not None
    assert Path(record.image.thumbnail_path).exists()


def test_recompose_a_fondo_blanco_con_background_path_none(tmp_path):
    job = _make_job_with_cutout(tmp_path)

    record = recompose_product_background(job, "p1", None, workdir=tmp_path)

    assert record.background_key is None
    composed = Image.open(record.image.composed_path)
    assert composed.getpixel((0, 0)) == (255, 255, 255)


def test_recompose_a_mantener_original_no_toca_rembg(tmp_path, monkeypatch):
    job = _make_job_with_cutout(tmp_path)
    source = tmp_path / "producto.jpg"
    Image.new("RGB", (50, 50), (5, 6, 7)).save(source, "JPEG")
    job.products[0].image.source_path = str(source)

    def _boom(*a, **kw):
        raise AssertionError("no debería llamar a remove_background en modo 'mantener original'")

    monkeypatch.setattr(pipeline_module, "remove_background", _boom)

    record = recompose_product_background(job, "p1", KEEP_ORIGINAL_BACKGROUND, workdir=tmp_path)

    assert record.background_key == KEEP_ORIGINAL_BACKGROUND
    composed = Image.open(record.image.composed_path)
    # tolerancia chica: la recodificación a JPEG (con pérdida) puede desviar
    # el valor de un canal en +/-1 respecto al RGB original.
    pixel = composed.getpixel((0, 0))
    assert all(abs(a - b) <= 2 for a, b in zip(pixel, (5, 6, 7), strict=True))


def test_recompose_calcula_el_recorte_si_falta_al_pasar_a_un_fondo_real(tmp_path, monkeypatch):
    """Un producto que se procesó con 'mantener original' no tiene cutout_path
    — si luego se le pide un fondo real, recompose debe calcularlo por primera
    vez en vez de fallar."""
    job = _make_job_with_cutout(tmp_path)
    job.products[0].image.cutout_path = None
    source = tmp_path / "producto.jpg"
    Image.new("RGB", (50, 50), (9, 9, 9)).save(source, "JPEG")
    job.products[0].image.source_path = str(source)

    calls = {"n": 0}

    def _fake_remove_background(image_path, output_path):
        calls["n"] += 1
        Image.new("RGBA", (40, 40), (0, 0, 0, 255)).save(output_path, "PNG")
        return output_path

    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)

    record = recompose_product_background(job, "p1", None, workdir=tmp_path)

    assert calls["n"] == 1
    assert record.image.cutout_path is not None
    assert Path(record.image.cutout_path).exists()


def test_recompose_falla_si_el_producto_no_existe(tmp_path):
    job = _make_job_with_cutout(tmp_path)

    try:
        recompose_product_background(job, "no-existe", None, workdir=tmp_path)
        raise AssertionError("debía lanzar ValueError")
    except ValueError:
        pass
