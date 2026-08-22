"""Prueba la lógica propia de los agentes sin llamar a Bedrock.

Sustituye el Agent de Strands por un doble de prueba que imita la forma real
de AgentResult (ver docs/03-revision-tecnica.md): un objeto con atributo `structured_output`.
Esto valida que armamos el mensaje/prompt correctamente y que desempacamos la
respuesta como corresponde — no valida que el modelo real responda bien, eso
requiere credenciales de AWS y se deja anotado como pendiente en docs/03-revision-tecnica.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from snapflick.agents.catalog_agent import plan_catalog
from snapflick.agents.vision_agent import extract_product_sheet
from snapflick.models.schemas import (
    CatalogPlan,
    CategoryAssignment,
    ProcessedImage,
    ProductRecord,
    ProductSheet,
)


@dataclass
class FakeAgentResult:
    structured_output: Any


class FakeAgent:
    """Imita `Agent.__call__(prompt, structured_output_model=...)` real de Strands."""

    def __init__(self, response: Any):
        self.response = response
        self.calls: list[tuple[Any, Any]] = []

    def __call__(self, prompt, *, structured_output_model=None, **kwargs):
        self.calls.append((prompt, structured_output_model))
        return FakeAgentResult(structured_output=self.response)


def test_extract_product_sheet_arma_bloque_de_imagen_correcto(tmp_path: Path):
    img_path = tmp_path / "producto.jpg"
    Image.new("RGB", (50, 50), (10, 20, 30)).save(img_path, "JPEG")

    expected = ProductSheet(name="Harina PAN", description="Harina de maíz precocida.")
    agent = FakeAgent(expected)

    result = extract_product_sheet(str(img_path), agent=agent)

    assert result is expected
    assert len(agent.calls) == 1
    message, model = agent.calls[0]
    assert model is ProductSheet
    assert message[0]["text"]
    assert message[1]["image"]["format"] == "jpeg"
    assert isinstance(message[1]["image"]["source"]["bytes"], bytes)


def test_extract_product_sheet_normaliza_extension_jpg_a_jpeg(tmp_path: Path):
    img_path = tmp_path / "producto.jpg"
    Image.new("RGB", (10, 10)).save(img_path, "JPEG")
    agent = FakeAgent(ProductSheet(name="x", description="y"))

    extract_product_sheet(str(img_path), agent=agent)

    _, model = agent.calls[0]
    assert model is ProductSheet


def test_plan_catalog_pasa_el_prompt_y_devuelve_structured_output():
    products = [
        ProductRecord(
            id="p1",
            sheet=ProductSheet(name="Refresco de cola", description="Bebida gaseosa 355 ml."),
            image=ProcessedImage(source_path="x.jpg"),
        ),
        ProductRecord(
            id="p2",
            sheet=ProductSheet(name="Agua mineral", description="Agua sin gas 500 ml."),
            image=ProcessedImage(source_path="y.jpg"),
        ),
    ]
    expected = CatalogPlan(
        categories=["Bebidas"],
        assignments=[
            CategoryAssignment(product_id="p1", category="Bebidas", reason="es una bebida"),
            CategoryAssignment(product_id="p2", category="Bebidas", reason="es una bebida"),
        ],
        catalog_title="Catálogo de bebidas",
        catalog_summary="Dos bebidas listas para publicar.",
    )
    agent = FakeAgent(expected)

    result = plan_catalog(products, agent=agent)

    assert result is expected
    prompt, model = agent.calls[0]
    assert model is CatalogPlan
    assert "p1" in prompt and "p2" in prompt
    assert "Refresco de cola" in prompt
