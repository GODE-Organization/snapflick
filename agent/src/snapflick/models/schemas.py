"""Contrato de datos compartido por agente, API y frontend."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ProductSheet(BaseModel):
    """Ficha de producto extraída del empaque.

    Regla de oro: si un dato no se ve en la imagen, el campo va en None.
    El agente NO inventa. La honestidad es parte del diseño.
    """

    name: str = Field(description="Nombre comercial del producto tal como aparece en el empaque")
    brand: str | None = Field(default=None, description="Marca. None si no es legible.")
    presentation: str | None = Field(
        default=None, description="Peso, volumen o unidades. Ej: '500 g', '1.5 L', '12 unidades'"
    )
    description: str = Field(description="Descripción breve y comercial, 1-2 frases, en español")
    category: str | None = Field(default=None, description="Categoría asignada por el CatalogAgent")
    keywords: list[str] = Field(default_factory=list, description="3-6 palabras clave de búsqueda")
    ingredients: str | None = None
    barcode: str | None = Field(default=None, description="Código de barras si es legible")
    language_detected: str | None = None
    confidence: Confidence = Field(
        default="medium", description="Confianza global de la extracción"
    )
    notes: str | None = Field(default=None, description="Qué no se pudo leer y por qué")


class ProcessedImage(BaseModel):
    source_path: str
    cutout_path: str | None = None  # PNG con transparencia
    composed_path: str | None = None  # JPG sobre fondo de marca
    thumbnail_path: str | None = None
    error: str | None = None


class ProductRecord(BaseModel):
    id: str
    sheet: ProductSheet
    image: ProcessedImage
    visible: bool = Field(
        default=True,
        description="Si es False, el producto se oculta del catálogo publicado sin borrarlo.",
    )
    background_key: str | None = Field(
        default=None,
        description="Path del fondo de marca compuesto sobre este producto. None = fondo blanco.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CategoryAssignment(BaseModel):
    product_id: str
    category: str
    reason: str


class CatalogPlan(BaseModel):
    """Salida del CatalogAgent: categorías coherentes para TODO el lote."""

    categories: list[str] = Field(
        description="Lista final de categorías, sin duplicados semánticos"
    )
    assignments: list[CategoryAssignment]
    catalog_title: str
    catalog_summary: str


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    # Dueño anónimo del job: el `sf_session` cookie-id que lo creó (ver
    # `main.py` `session_dependency`). `None` = job creado antes de este
    # campo existir — se trata como accesible/editable por cualquiera para no
    # romper catálogos ya publicados en producción.
    session_id: str | None = None
    background_key: str | None = None
    total_images: int = 0
    processed_images: int = 0
    products: list[ProductRecord] = Field(default_factory=list)
    plan: CatalogPlan | None = None
    catalog_html_path: str | None = None
    catalog_json_path: str | None = None
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
