"""Construye el modelo multimodal que usan VisionAgent y CatalogAgent.

Bedrock es el proveedor por defecto. Gemini existe como alternativa mientras se
resuelve el acceso a Bedrock (bloqueo geográfico de Anthropic y/o cuota de
Bedrock en 0 para modelos Nova — ver docs/03-revision-tecnica.md): cambiar de
proveedor es solo `SNAPFLICK_MODEL_PROVIDER=gemini` + `SNAPFLICK_GEMINI_API_KEY`
en `.env`, sin tocar ningún agente.
"""

from __future__ import annotations

from strands.models import BedrockModel
from strands.models.model import Model

from .config import settings


def build_model() -> Model:
    if settings.model_provider == "gemini":
        from strands.models.gemini import GeminiModel

        if not settings.gemini_api_key:
            raise ValueError(
                "SNAPFLICK_MODEL_PROVIDER=gemini requiere SNAPFLICK_GEMINI_API_KEY en .env"
            )
        return GeminiModel(
            client_args={"api_key": settings.gemini_api_key},
            model_id=settings.gemini_model_id,
        )

    return BedrockModel(model_id=settings.bedrock_model_id, region_name=settings.aws_region)
