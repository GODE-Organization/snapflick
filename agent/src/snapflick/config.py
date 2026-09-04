from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SNAPFLICK_", extra="ignore")

    # Proveedor del modelo multimodal usado por VisionAgent/CatalogAgent.
    # None (sin setear) => modo automático: se prueba cada proveedor en orden
    # (bedrock -> gemini -> chatgpt -> ollama) con una llamada real mínima; el
    # primero que responde gana y esa elección se cachea para el resto del
    # proceso. Si se fija explícitamente, solo se intenta ese proveedor y
    # cualquier falla se propaga tal cual (sin fallback). Ver model_provider.py.
    model_provider: Literal["bedrock", "gemini", "chatgpt", "ollama"] | None = None

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    s3_bucket: str | None = None  # None => almacenamiento local

    # Gemini
    gemini_api_key: str | None = None
    gemini_model_id: str = "gemini-2.5-flash"

    # ChatGPT / OpenAI
    chatgpt_api_key: str | None = None
    chatgpt_model_id: str = "gpt-4o-mini"

    # Ollama (servidor local u on-prem). El modelo debe soportar imágenes
    # (p.ej. "llama3.2-vision", "llava", "qwen2.5vl") — VisionAgent lee fotos.
    ollama_host: str = "http://localhost:11434"
    ollama_model_id: str = "llama3.2-vision"

    # Almacenamiento local (desarrollo)
    data_dir: Path = Path("./data")

    # Imagen
    rembg_model: str = "isnet-general-use"
    canvas_size: int = 1200  # lienzo cuadrado de salida
    product_margin: float = 0.10  # 10% de margen alrededor del producto
    thumbnail_size: int = 400

    # App
    max_images_per_job: int = 30
    log_level: str = "INFO"

    # Orígenes permitidos para CORS *con* credenciales (cookie de sesión), separados
    # por coma. "*" no es válido junto con allow_credentials=True (lo rechaza el
    # navegador), así que a diferencia del resto de settings esto no tiene un default
    # abierto — ver main.py `_cors_origins()`.
    cors_origins: str = "http://localhost:3000"


settings = Settings()
