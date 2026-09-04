"""Regresión: al recomponer un producto con otro fondo, `main.py` reescribe
`composed_path`/`thumbnail_path` con el MISMO nombre de archivo — sin un
cache-buster en la URL, el navegador sigue sirviendo la imagen vieja desde su
caché en las vistas de administración, aunque el catálogo HTML publicado
(que incrusta bytes frescos en base64) sí se vea actualizado. Ver
`ProcessedImage.version` / `_to_url(path, version=...)`."""

from __future__ import annotations

from pathlib import Path

import snapflick.main as main_module
from snapflick.models.schemas import Job, JobStatus, ProcessedImage, ProductRecord, ProductSheet


def _make_job(tmp_path: Path, version: int) -> Job:
    composed = tmp_path / "producto.jpg"
    composed.write_bytes(b"fake-jpg")
    record = ProductRecord(
        id="p1",
        sheet=ProductSheet(name="Producto", description="Descripción de prueba."),
        image=ProcessedImage(
            source_path=str(tmp_path / "original.jpg"),
            composed_path=str(composed),
            thumbnail_path=str(composed),
            version=version,
        ),
    )
    return Job(
        id="job-1", status=JobStatus.DONE, total_images=1, processed_images=1, products=[record]
    )


def test_job_to_public_dict_agrega_version_a_composed_y_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(main_module.settings, "s3_bucket", None)
    monkeypatch.setattr(main_module, "DATA", tmp_path)
    job = _make_job(tmp_path, version=3)

    data = main_module.job_to_public_dict(job)

    img = data["products"][0]["image"]
    assert img["composed_path"].endswith("?v=3")
    assert img["thumbnail_path"].endswith("?v=3")
    # source_path nunca se reescribe con el mismo nombre, no necesita cache-buster
    assert "?v=" not in (img["source_path"] or "")


def test_la_url_cambia_cuando_version_avanza(tmp_path, monkeypatch):
    """Es justo lo que fuerza al navegador a pedir el archivo de nuevo en vez
    de reusar la respuesta cacheada de la URL anterior."""
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(main_module.settings, "s3_bucket", None)
    monkeypatch.setattr(main_module, "DATA", tmp_path)

    url_v1 = main_module.job_to_public_dict(_make_job(tmp_path, version=1))["products"][0]["image"][
        "composed_path"
    ]
    url_v2 = main_module.job_to_public_dict(_make_job(tmp_path, version=2))["products"][0]["image"][
        "composed_path"
    ]

    assert url_v1 != url_v2


def test_no_agrega_version_a_urls_firmadas_de_s3(tmp_path, monkeypatch):
    """Una presigned URL de S3 ya trae su propia query string de firma
    (y cambia en cada llamada) — agregarle `?v=` la rompería."""
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(main_module.settings, "s3_bucket", "fake-bucket")
    monkeypatch.setattr(main_module, "DATA", tmp_path)
    monkeypatch.setattr(
        main_module,
        "get_storage",
        lambda: type(
            "FakeStorage",
            (),
            {"url": staticmethod(lambda key: f"https://s3.example/{key}?X-Amz-Signature=abc")},
        )(),
    )
    job = _make_job(tmp_path, version=5)

    data = main_module.job_to_public_dict(job)

    composed_url = data["products"][0]["image"]["composed_path"]
    assert composed_url == "https://s3.example/producto.jpg?X-Amz-Signature=abc"
    assert "v=5" not in composed_url


def test_recompose_incrementa_la_version(tmp_path):
    from PIL import Image

    from snapflick.pipeline import recompose_product_background

    cutout = tmp_path / "cutout.png"
    Image.new("RGBA", (50, 50), (0, 0, 0, 255)).save(cutout, "PNG")
    record = ProductRecord(
        id="p1",
        sheet=ProductSheet(name="Producto", description="Descripción de prueba."),
        image=ProcessedImage(source_path=str(tmp_path / "producto.jpg"), cutout_path=str(cutout)),
    )
    job = Job(
        id="job-1", status=JobStatus.DONE, total_images=1, processed_images=1, products=[record]
    )
    assert record.image.version == 1

    recompose_product_background(job, "p1", None, workdir=tmp_path)

    assert record.image.version == 2
