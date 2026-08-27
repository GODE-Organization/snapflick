"""CatalogAgent: decide categorías coherentes para TODO el lote de una vez.

Categorizar producto por producto produce 'Bebida', 'Bebidas' y 'Refrescos'
como tres categorías distintas. Categorizar el lote completo evita eso.
"""

from __future__ import annotations

from strands import Agent

from ..model_provider import build_model
from ..models.schemas import CatalogPlan, ProductRecord

SEED_TAXONOMY = [
    "Abarrotes",
    "Bebidas",
    "Snacks y golosinas",
    "Limpieza del hogar",
    "Cuidado personal",
    "Lácteos y refrigerados",
    "Panadería",
    "Mascotas",
    "Bebés",
    "Otros",
]

SYSTEM_PROMPT = f"""Eres un merchandiser que organiza catálogos de productos.

Recibes la lista completa de productos de un lote y devuelves un plan de catálogo.

Reglas:
1. Usa preferentemente esta taxonomía semilla: {", ".join(SEED_TAXONOMY)}.
   Puedes crear una categoría nueva SOLO si al menos 2 productos no encajan en ninguna.
2. Nunca devuelvas dos categorías que signifiquen lo mismo.
3. Toda categoría en 'categories' debe tener al menos un producto asignado,
   y todo producto debe recibir exactamente una categoría.
4. Ordena 'categories' de mayor a menor cantidad de productos.
5. catalog_title y catalog_summary deben ser comerciales y en español,
   describiendo el conjunto real de productos recibidos.
"""


def build_catalog_agent() -> Agent:
    return Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)


def plan_catalog(products: list[ProductRecord], agent: Agent | None = None) -> CatalogPlan:
    agent = agent or build_catalog_agent()
    listado = "\n".join(
        f"- id={p.id} | nombre={p.sheet.name} | marca={p.sheet.brand or 'desconocida'} "
        f"| presentacion={p.sheet.presentation or '-'} | desc={p.sheet.description}"
        for p in products
    )
    prompt = f"Organiza este lote de {len(products)} productos:\n\n{listado}"
    result = agent(prompt, structured_output_model=CatalogPlan)
    return result.structured_output
