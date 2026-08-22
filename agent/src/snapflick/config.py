from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SNAPFLICK_", extra="ignore")

    # AWS
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    s3_bucket: str | None = None  # None => almacenamiento local

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


settings = Settings()
