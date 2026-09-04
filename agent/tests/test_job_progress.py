"""Regresión del hallazgo #1 de docs/03-revision-tecnica.md: el progreso del job debe
verse mientras el lote se procesa, no solo al final.

Se reemplazan las herramientas de imagen y los agentes por dobles rápidos
(nada de rembg ni Bedrock) para poder aislar exactamente el comportamiento que
se rompía: `JOBS[job_id]` tiene que ser el mismo objeto que `run_job` va
mutando, así que `processed_images` avanza de verdad mientras corre el lote.
"""

from __future__ import annotations

from pathlib import Path

import snapflick.main as main_module
import snapflick.pipeline as pipeline_module
from snapflick.db import JobStore
from snapflick.models.schemas import CatalogPlan, CategoryAssignment, Job, JobStatus, ProductSheet


def _fake_extract_product_sheet(path, agent=None):
    return ProductSheet(name="Producto de prueba", description="Descripción de prueba.")


def _fake_plan_catalog(products, agent=None):
    return CatalogPlan(
        categories=["Otros"],
        assignments=[
            CategoryAssignment(product_id=p.id, category="Otros", reason="prueba") for p in products
        ],
        catalog_title="Catálogo de prueba",
        catalog_summary="Resumen de prueba.",
    )


def _fake_remove_background(image_path: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(b"fake-png")
    return output_path


def _fake_compose_on_background(cutout_path, background_path, output_path) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(b"fake-jpg")
    return output_path


def _fake_make_thumbnail(image_path, output_path) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(b"fake-thumb")
    return output_path


def _fake_keep_original(image_path, output_path) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(b"fake-original")
    return output_path


def test_run_job_muta_el_mismo_objeto_que_recibe(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _fake_compose_on_background)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _fake_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "build_vision_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "build_catalog_agent", lambda: None)
    # el caché de extracción mete el proveedor/modelo resuelto en la clave;
    # sin esto, `_cached_extract_product_sheet` dispararía una resolución real
    # de proveedor (red) en medio de un test que no debería tocar la red.
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(pipeline_module.settings, "data_dir", tmp_path)

    job = Job(id="job-progress", total_images=3)
    image_paths = [str(tmp_path / f"foto{i}.jpg") for i in range(3)]
    for p in image_paths:
        Path(p).write_bytes(b"fake-source")

    result = pipeline_module.run_job(job, image_paths, workdir=tmp_path)

    assert result is job, "run_job debe mutar y devolver el mismo objeto que recibió"
    assert job.processed_images == 3
    assert job.status == JobStatus.DONE
    assert len(job.products) == 3


def test_process_actualiza_el_job_que_vive_en_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _fake_compose_on_background)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _fake_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "build_vision_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "build_catalog_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    # STORE ya se construyó al importar main.py, apuntando al data_dir real —
    # redirigirlo aquí evita que este test escriba jobs falsos en la base de
    # datos de desarrollo.
    monkeypatch.setattr(main_module, "STORE", JobStore(tmp_path / "jobs.db"))

    job_id = "job-abc"
    job = Job(id=job_id, total_images=2)
    main_module.JOBS[job_id] = job

    image_paths = [str(tmp_path / f"foto{i}.jpg") for i in range(2)]
    for p in image_paths:
        Path(p).write_bytes(b"fake-source")

    main_module._process(job_id, image_paths, None)

    # esta es exactamente la regresión: JOBS[job_id] tiene que reflejar el
    # avance real, no seguir siendo el objeto "pending" original sin tocar.
    assert main_module.JOBS[job_id] is job
    assert main_module.JOBS[job_id].processed_images == 2
    assert main_module.JOBS[job_id].status == JobStatus.DONE

    del main_module.JOBS[job_id]


def test_run_job_reusa_el_cache_de_extraccion_para_la_misma_imagen(tmp_path, monkeypatch):
    """Regresión del punto 6 del pedido: repetir el job con la misma imagen no
    debe volver a llamar al modelo de IA (reutiliza la extracción cacheada)."""
    calls = {"n": 0}

    def _counting_extract_product_sheet(path, agent=None):
        calls["n"] += 1
        return _fake_extract_product_sheet(path, agent)

    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _fake_compose_on_background)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _counting_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "build_vision_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "build_catalog_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(pipeline_module.settings, "data_dir", tmp_path)

    image_path = tmp_path / "same_photo.jpg"
    image_path.write_bytes(b"identical-bytes")

    job1 = Job(id="job-cache-1", total_images=1)
    pipeline_module.run_job(job1, [str(image_path)], workdir=tmp_path)

    job2 = Job(id="job-cache-2", total_images=1)
    pipeline_module.run_job(job2, [str(image_path)], workdir=tmp_path)

    assert calls["n"] == 1, "la segunda corrida con la misma imagen debió reutilizar el caché"
    assert len(job1.products) == 1
    assert len(job2.products) == 1


def test_run_job_asigna_fondo_por_imagen(tmp_path, monkeypatch):
    """`per_image_backgrounds` debe ganarle al `background_path` por defecto
    para las fotos que sí aparecen en el mapa, y las demás deben caer de
    vuelta al default — así cada producto del lote puede llevar un fondo
    distinto."""
    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _fake_compose_on_background)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _fake_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "build_vision_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "build_catalog_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(pipeline_module.settings, "data_dir", tmp_path)

    image_paths = [str(tmp_path / f"foto{i}.jpg") for i in range(2)]
    for p in image_paths:
        Path(p).write_bytes(b"fake-source")

    job = Job(id="job-per-image-bg", total_images=2)
    pipeline_module.run_job(
        job,
        image_paths,
        background_path="/default/bg.jpg",
        workdir=tmp_path,
        per_image_backgrounds={image_paths[0]: "/other/bg.jpg"},
    )

    by_source = {p.image.source_path: p for p in job.products}
    assert by_source[image_paths[0]].background_key == "/other/bg.jpg"
    assert by_source[image_paths[1]].background_key == "/default/bg.jpg"


def test_run_job_mantener_original_no_llama_a_remove_background(tmp_path, monkeypatch):
    """`KEEP_ORIGINAL_BACKGROUND` debe saltarse rembg y `compose_on_background`
    por completo — la foto se usa tal cual."""

    def _boom(*a, **kw):
        raise AssertionError("no debería llamar a remove_background en modo 'mantener original'")

    monkeypatch.setattr(pipeline_module, "remove_background", _boom)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _boom)
    monkeypatch.setattr(pipeline_module, "keep_original", _fake_keep_original)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _fake_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "build_vision_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "build_catalog_agent", lambda: None)
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(pipeline_module.settings, "data_dir", tmp_path)

    image_path = tmp_path / "foto.jpg"
    image_path.write_bytes(b"fake-source")

    job = Job(id="job-keep-original", total_images=1)
    pipeline_module.run_job(
        job,
        [str(image_path)],
        background_path=pipeline_module.KEEP_ORIGINAL_BACKGROUND,
        workdir=tmp_path,
    )

    assert job.products[0].background_key == pipeline_module.KEEP_ORIGINAL_BACKGROUND
    assert job.products[0].image.cutout_path is None


def test_cache_key_cambia_si_cambia_el_prompt_o_el_proveedor(monkeypatch):
    """La clave del caché de extracción debe invalidarse sola si se ajusta el
    prompt o cambia el proveedor/modelo resuelto — no solo si cambia la
    imagen. Ver PROMPT_VERSION en agents/vision_agent.py."""
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "gemini")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "gemini-2.5-flash")
    monkeypatch.setattr(pipeline_module, "PROMPT_VERSION", "v1")
    image_bytes = b"same-image-bytes"

    key_v1 = pipeline_module._cache_key(image_bytes)

    monkeypatch.setattr(pipeline_module, "PROMPT_VERSION", "v2")
    key_v2 = pipeline_module._cache_key(image_bytes)

    monkeypatch.setattr(pipeline_module, "PROMPT_VERSION", "v1")
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "chatgpt")
    key_other_provider = pipeline_module._cache_key(image_bytes)

    assert len({key_v1, key_v2, key_other_provider}) == 3
