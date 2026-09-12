"""Reglas de agente definidas por el usuario (ver /ajustes-ia): un blob JSON por
`session_id`, igual que el fondo por defecto (ver test_background_ownership.py), más
su inyección en los prompts de VisionAgent/CatalogAgent y su efecto en el caché de
extracción (ver "Gemini rate limits and extraction caching" en CLAUDE.md)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import snapflick.agents.catalog_agent as catalog_agent_module
import snapflick.agents.vision_agent as vision_agent_module
import snapflick.main as main_module
import snapflick.pipeline as pipeline_module
from snapflick.agent_settings import get_agent_settings, save_agent_settings
from snapflick.agents.catalog_agent import SYSTEM_PROMPT as CATALOG_SYSTEM_PROMPT
from snapflick.agents.catalog_agent import build_catalog_agent
from snapflick.agents.vision_agent import SYSTEM_PROMPT as VISION_SYSTEM_PROMPT
from snapflick.agents.vision_agent import build_vision_agent
from snapflick.models.schemas import AgentSettings, Job, JobStatus, ProductSheet


@pytest.fixture(autouse=True)
def _fake_model(monkeypatch):
    """`build_vision_agent`/`build_catalog_agent` llaman `build_model()`, que en
    CI no tiene ningún proveedor real disponible (sin credenciales AWS, sin
    `google-genai`/`openai`/`ollama` instalados — ver model_provider.py). Estos
    tests solo verifican la construcción del `system_prompt`, nunca hacen una
    llamada real al modelo, así que alcanza con un `Model` de Strands de juguete
    en vez de resolver un proveedor de verdad."""
    from strands.models.model import Model

    fake_model = MagicMock(spec=Model)
    fake_model.stateful = False
    monkeypatch.setattr(vision_agent_module, "build_model", lambda: fake_model)
    monkeypatch.setattr(catalog_agent_module, "build_model", lambda: fake_model)


def _setup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    # Sin esto, un `.env` de dev con SNAPFLICK_S3_BUCKET real haría que
    # get_storage() devuelva S3Storage y los settings se guarden/lean contra
    # el bucket de verdad en vez de aislarse en tmp_path.
    monkeypatch.setattr(main_module.settings, "s3_bucket", None)


def test_get_agent_settings_sin_sesion_devuelve_default_sin_tocar_storage(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert get_agent_settings(None) == AgentSettings()


def test_get_agent_settings_sin_guardar_devuelve_default(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert get_agent_settings("session-nueva") == AgentSettings()


def test_save_y_get_agent_settings_hacen_roundtrip(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    saved = save_agent_settings(
        "session-a", AgentSettings(product_rules="nunca menciones precios", catalog_rules="")
    )
    assert saved.product_rules == "nunca menciones precios"
    assert get_agent_settings("session-a").product_rules == "nunca menciones precios"


def test_agent_settings_estan_aisladas_por_sesion(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    save_agent_settings("session-a", AgentSettings(product_rules="regla de A"))
    save_agent_settings("session-b", AgentSettings(product_rules="regla de B"))

    assert get_agent_settings("session-a").product_rules == "regla de A"
    assert get_agent_settings("session-b").product_rules == "regla de B"


def test_ruta_get_settings_devuelve_default_vacio(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    assert main_module.get_settings(session_id="session-x") == AgentSettings()


def test_ruta_patch_settings_mergea_y_persiste(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    from snapflick.main import AgentSettingsUpdate

    main_module.update_settings(
        AgentSettingsUpdate(product_rules="tono formal"), session_id="session-x"
    )
    updated = main_module.update_settings(
        AgentSettingsUpdate(catalog_rules="agrupa bebidas y snacks juntos"),
        session_id="session-x",
    )

    # el segundo PATCH solo tocó catalog_rules — product_rules del primero se conserva
    assert updated.product_rules == "tono formal"
    assert updated.catalog_rules == "agrupa bebidas y snacks juntos"
    assert main_module.get_settings(session_id="session-x") == updated


def test_build_vision_agent_sin_reglas_no_toca_el_prompt_base():
    agent = build_vision_agent()
    assert agent.system_prompt == VISION_SYSTEM_PROMPT


def test_build_vision_agent_appendea_las_reglas_del_usuario():
    agent = build_vision_agent("nunca menciones el precio")
    assert agent.system_prompt.startswith(VISION_SYSTEM_PROMPT)
    assert "nunca menciones el precio" in agent.system_prompt


def test_build_vision_agent_ignora_reglas_en_blanco():
    agent = build_vision_agent("   ")
    assert agent.system_prompt == VISION_SYSTEM_PROMPT


def test_build_catalog_agent_appendea_las_reglas_del_usuario():
    agent = build_catalog_agent("agrupa bebidas y snacks juntos")
    assert agent.system_prompt.startswith(CATALOG_SYSTEM_PROMPT)
    assert "agrupa bebidas y snacks juntos" in agent.system_prompt


def test_cache_key_cambia_si_cambian_las_reglas_del_usuario(monkeypatch):
    """Mismo criterio que ya cubre `PROMPT_VERSION`/proveedor en
    test_job_progress.py: cambiar las reglas de /ajustes-ia debe invalidar el
    caché de extracción en vez de seguir sirviendo resultados con reglas viejas."""
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "gemini")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "gemini-2.5-flash")
    image_bytes = b"same-image-bytes"

    key_sin_reglas = pipeline_module._cache_key(image_bytes)
    key_con_reglas = pipeline_module._cache_key(image_bytes, "nunca menciones el precio")
    key_otras_reglas = pipeline_module._cache_key(image_bytes, "usa tono formal")

    assert len({key_sin_reglas, key_con_reglas, key_otras_reglas}) == 3


def test_add_product_to_job_usa_la_sesion_de_quien_agrega_no_la_del_job_legacy(
    tmp_path, monkeypatch
):
    """Regresión: un job publicado antes de que `Job.session_id` existiera
    (`session_id=None`, ver `models/schemas.py`) no debe ignorar las reglas
    de /ajustes-ia del visitante actual al agregarle un producto nuevo —
    `main.py` ahora pasa explícitamente el `session_id` de la request, en vez
    de que `add_product_to_job` caiga de vuelta a `job.session_id` (siempre
    `None` para esos jobs, sin importar quién esté agregando el producto)."""
    calls: dict[str, str | None] = {}

    def _fake_get_agent_settings(session_id):
        calls["session_id"] = session_id
        return AgentSettings(product_rules="regla del visitante actual")

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

    def _fake_extract_product_sheet(path, agent=None):
        return ProductSheet(name="Producto nuevo", description="Descripción de prueba.")

    def _fake_plan_catalog(products, agent=None):
        from snapflick.models.schemas import CatalogPlan, CategoryAssignment

        return CatalogPlan(
            categories=["Otros"],
            assignments=[
                CategoryAssignment(product_id=p.id, category="Otros", reason="prueba")
                for p in products
            ],
            catalog_title="Catálogo de prueba",
            catalog_summary="Resumen de prueba.",
        )

    monkeypatch.setattr(pipeline_module, "get_agent_settings", _fake_get_agent_settings)
    monkeypatch.setattr(pipeline_module, "remove_background", _fake_remove_background)
    monkeypatch.setattr(pipeline_module, "compose_on_background", _fake_compose_on_background)
    monkeypatch.setattr(pipeline_module, "make_thumbnail", _fake_make_thumbnail)
    monkeypatch.setattr(pipeline_module, "extract_product_sheet", _fake_extract_product_sheet)
    monkeypatch.setattr(pipeline_module, "plan_catalog", _fake_plan_catalog)
    monkeypatch.setattr(pipeline_module, "resolved_provider", lambda: "fake")
    monkeypatch.setattr(pipeline_module, "resolved_model_id", lambda: "fake-model")
    monkeypatch.setattr(pipeline_module.settings, "data_dir", tmp_path)

    job = Job(id="legacy-job", status=JobStatus.DONE, session_id=None)
    image_path = tmp_path / "nuevo.jpg"
    image_path.write_bytes(b"fake-source")

    pipeline_module.add_product_to_job(job, str(image_path), session_id="current-visitor")

    assert calls["session_id"] == "current-visitor"
