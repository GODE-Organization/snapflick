"""GET /public/jobs/{job_id}: la vista pública del catálogo (`web/src/app/c/[jobId]`),
sin cookie de sesión ni chequeo de dueño — mismo modelo de exposición sin auth que hoy
tiene `catalog_html_path` vía /files (ver CLAUDE.md, "Catálogo HTML es autocontenido"),
pero como datos en vez de HTML."""

from __future__ import annotations

import snapflick.main as main_module
from snapflick.models.schemas import (
    CatalogPlan,
    CategoryAssignment,
    Job,
    JobStatus,
    ProcessedImage,
    ProductRecord,
    ProductSheet,
)


def _product(id: str, *, category: str, visible: bool = True) -> ProductRecord:
    return ProductRecord(
        id=id,
        sheet=ProductSheet(
            name=f"Producto {id}",
            brand="Marca X",
            presentation="500 g",
            description=f"Descripción de {id}.",
            keywords=["uno", "dos"],
        ),
        image=ProcessedImage(
            source_path=f"/tmp/{id}.jpg", composed_path=f"/tmp/{id}-compuesto.jpg"
        ),
        visible=visible,
    )


def _done_job(job_id: str, products: list[ProductRecord], categories: list[str]) -> Job:
    return Job(
        id=job_id,
        status=JobStatus.DONE,
        products=products,
        plan=CatalogPlan(
            categories=categories,
            assignments=[
                CategoryAssignment(
                    product_id=p.id, category=p.sheet.category or categories[0], reason="prueba"
                )
                for p in products
            ],
            catalog_title="Catálogo de prueba",
            catalog_summary="Resumen de prueba.",
        ),
    )


def test_devuelve_404_si_el_job_no_existe():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        main_module.get_public_catalog("no-existe")
    assert exc.value.status_code == 404


def test_devuelve_404_si_el_job_todavia_no_esta_listo(monkeypatch):
    import pytest
    from fastapi import HTTPException

    job = _done_job("job-1", [], ["Otros"])
    job.status = JobStatus.PROCESSING
    monkeypatch.setitem(main_module.JOBS, "job-1", job)

    with pytest.raises(HTTPException) as exc:
        main_module.get_public_catalog("job-1")
    assert exc.value.status_code == 404


def test_excluye_productos_ocultos_y_respeta_el_orden_de_categorias(monkeypatch):
    p_bebida = _product("p-bebida", category="Bebidas")
    p_bebida.sheet.category = "Bebidas"
    p_snack = _product("p-snack", category="Snacks")
    p_snack.sheet.category = "Snacks"
    p_oculto = _product("p-oculto", category="Snacks", visible=False)
    p_oculto.sheet.category = "Snacks"

    job = _done_job(
        "job-2",
        [p_snack, p_bebida, p_oculto],
        categories=["Bebidas", "Snacks"],
    )
    monkeypatch.setitem(main_module.JOBS, "job-2", job)

    result = main_module.get_public_catalog("job-2")

    assert [p.id for p in result.products] == ["p-bebida", "p-snack"]
    assert result.catalog_title == "Catálogo de prueba"
    assert result.categories == ["Bebidas", "Snacks"]


def test_no_requiere_sesion_ni_dueno(monkeypatch):
    """A diferencia de GET /jobs/{id}, esta ruta no toma `session_id` como
    parámetro — no hay forma de que dependa de una cookie."""
    import inspect

    params = inspect.signature(main_module.get_public_catalog).parameters
    assert "session_id" not in params
