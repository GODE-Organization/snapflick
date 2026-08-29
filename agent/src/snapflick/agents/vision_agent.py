"""VisionAgent: lee el empaque y devuelve una ProductSheet validada.

Usa salida estructurada de Strands: el modelo devuelve directamente el objeto
Pydantic, no texto que haya que parsear. Esto elimina la clase de bug más común
del proyecto.
"""

from __future__ import annotations

from pathlib import Path

from strands import Agent

from ..model_provider import build_model
from ..models.schemas import ProductSheet

# Cambiar a mano cada vez que SYSTEM_PROMPT cambie de forma que afecte el
# resultado de la extracción. Entra en la clave del caché de extracción
# (ver pipeline.py/retry.py) para que un cambio de prompt no siga sirviendo
# resultados cacheados con el prompt viejo.
PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """Eres un catalogador experto de productos de retail.

Recibes la foto de un producto y extraes SOLO lo que realmente se ve en el empaque.

Reglas estrictas:
1. NUNCA inventes datos. Si la marca no es legible, brand = null.
2. La descripción debe ser comercial y breve (1-2 frases), en español, apta para
   publicar en un catálogo. Nada de "la imagen muestra..." ni "se observa...".
3. presentation debe incluir la unidad: "500 g", "1.5 L", "12 unidades".
4. keywords: 3 a 6 términos que un comprador escribiría al buscar el producto.
5. confidence refleja la legibilidad real de la foto:
   - high: empaque nítido y frontal, texto legible
   - medium: parcialmente legible o en ángulo
   - low: borroso, muy lejano, o el producto no se distingue
6. En notes, indica qué no pudiste leer y por qué. Es información valiosa
   para el usuario, no una disculpa.
"""


def build_vision_agent() -> Agent:
    return Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)


def extract_product_sheet(image_path: str, agent: Agent | None = None) -> ProductSheet:
    """Extrae la ficha de producto a partir de la foto original."""
    agent = agent or build_vision_agent()
    path = Path(image_path)
    image_format = path.suffix.lstrip(".").lower()
    if image_format in ("jpg", "jpeg"):
        image_format = "jpeg"

    message = [
        {"text": "Extrae la ficha de este producto siguiendo tus reglas."},
        {"image": {"format": image_format, "source": {"bytes": path.read_bytes()}}},
    ]
    result = agent(message, structured_output_model=ProductSheet)
    return result.structured_output
