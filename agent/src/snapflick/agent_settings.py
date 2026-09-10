"""Reglas de agente definidas por el usuario, por sesión anónima.

Mismo patrón que `main.py._get_default_background_key`/`_set_default_background_key`:
un blob JSON chico en `Storage`, no una fila en `Job`/SQLite — es un ajuste del visitante,
no de un job en particular. Vive en su propio módulo (en vez de `main.py`) porque
`pipeline.py` también necesita leerlo para construir los agentes con las reglas activas.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .models.schemas import AgentSettings
from .paths import agent_settings_key
from .tools.storage_tools import get_storage


def get_agent_settings(session_id: str | None) -> AgentSettings:
    """Reglas guardadas para `session_id`, o `AgentSettings()` (reglas vacías) si no
    hay sesión (jobs/requests legacy sin cookie) o todavía no guardó nada."""
    if not session_id:
        return AgentSettings()
    storage = get_storage()
    key = agent_settings_key(session_id)
    if not storage.exists(key):
        return AgentSettings()
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "settings.json"
        storage.fetch(key, str(dest))
        return AgentSettings.model_validate_json(dest.read_text(encoding="utf-8"))


def save_agent_settings(session_id: str, settings: AgentSettings) -> AgentSettings:
    storage = get_storage()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "settings.json"
        src.write_text(json.dumps(settings.model_dump()), encoding="utf-8")
        storage.save(str(src), agent_settings_key(session_id))
    return settings
