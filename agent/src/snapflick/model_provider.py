"""Construye el modelo multimodal que usan VisionAgent y CatalogAgent.

Cuatro proveedores soportados: bedrock, gemini, chatgpt (OpenAI), ollama.

Si `SNAPFLICK_MODEL_PROVIDER` está seteada, se usa exclusivamente ese
proveedor — si falla (credenciales, cuota, red), el error se propaga tal
cual, sin intentar otro.

Si NO está seteada (modo automático), se prueban en orden: bedrock -> gemini
-> chatgpt -> ollama. "Probar" significa construir el modelo y hacer una
llamada real mínima; el primero que responde sin lanzar excepción gana. Esa
elección se cachea a nivel de proceso (no se vuelve a probar en cada job) —
ver `_resolved_model`.
"""

from __future__ import annotations

import logging

from strands import Agent
from strands.models import BedrockModel
from strands.models.model import Model

from .config import settings

log = logging.getLogger(__name__)

FALLBACK_ORDER = ["bedrock", "gemini", "chatgpt", "ollama"]

_resolved_provider: str | None = None
_resolved_model: Model | None = None


def _build_bedrock() -> Model:
    return BedrockModel(model_id=settings.bedrock_model_id, region_name=settings.aws_region)


def _build_gemini() -> Model:
    from strands.models.gemini import GeminiModel

    if not settings.gemini_api_key:
        raise ValueError("Falta SNAPFLICK_GEMINI_API_KEY")
    return GeminiModel(
        client_args={"api_key": settings.gemini_api_key},
        model_id=settings.gemini_model_id,
    )


def _build_chatgpt() -> Model:
    from strands.models.openai import OpenAIModel

    if not settings.chatgpt_api_key:
        raise ValueError("Falta SNAPFLICK_CHATGPT_API_KEY")
    return OpenAIModel(
        client_args={"api_key": settings.chatgpt_api_key},
        model_id=settings.chatgpt_model_id,
    )


def _build_ollama() -> Model:
    from strands.models.ollama import OllamaModel

    return OllamaModel(settings.ollama_host, model_id=settings.ollama_model_id)


_BUILDERS = {
    "bedrock": _build_bedrock,
    "gemini": _build_gemini,
    "chatgpt": _build_chatgpt,
    "ollama": _build_ollama,
}


def _probe(model: Model) -> None:
    """Llamada real mínima para confirmar que el proveedor responde. Lanza si
    no está disponible (credenciales, cuota, red, paquete no instalado)."""
    Agent(model=model, system_prompt="Responde únicamente con la palabra ok.")("ping")


def build_model() -> Model:
    global _resolved_provider, _resolved_model
    if _resolved_model is not None:
        return _resolved_model

    if settings.model_provider:
        model = _BUILDERS[settings.model_provider]()
        _resolved_provider, _resolved_model = settings.model_provider, model
        return model

    failures: list[str] = []
    for name in FALLBACK_ORDER:
        try:
            model = _BUILDERS[name]()
            _probe(model)
        except Exception as exc:  # este proveedor no sirve, se prueba el siguiente
            failures.append(f"{name}: {exc}")
            log.warning("Proveedor de modelo '%s' no disponible: %s", name, exc)
            continue
        log.info("Proveedor de modelo resuelto automáticamente: %s", name)
        _resolved_provider, _resolved_model = name, model
        return model

    raise RuntimeError(
        "Ningún proveedor de modelo está disponible (SNAPFLICK_MODEL_PROVIDER no está "
        "seteada, así que se probaron todos). Intentos:\n" + "\n".join(failures)
    )
