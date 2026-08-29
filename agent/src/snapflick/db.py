"""Persistencia de Jobs en SQLite.

`Job` ya es un árbol pydantic autocontenido que el resto del código muta en el
sitio (ver `pipeline.run_job` y la nota "Job mutation, not replacement" en
CLAUDE.md) — así que en vez de modelarlo como tablas relacionales separadas
para products/plan, cada fila guarda el Job completo serializado en JSON.
`status` y `created_at` se duplican en columnas propias solo para poder
ordenar `GET /jobs` sin deserializar cada fila.

Cada método abre su propia conexión: `JobStore` puede llamarse tanto desde el
request principal como desde el `BackgroundTasks` que procesa el lote (hilos
distintos), y las conexiones sqlite3 no son seguras para compartir entre
threads.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .models.schemas import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


class JobStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def save(self, job: Job) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, status, created_at, data) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET status = excluded.status, data = excluded.data
                """,
                (job.id, job.status.value, job.created_at.isoformat(), job.model_dump_json()),
            )

    def get(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def all(self) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM jobs ORDER BY created_at DESC").fetchall()
        return [Job.model_validate_json(row[0]) for row in rows]
