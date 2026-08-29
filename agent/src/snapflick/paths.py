"""Convención única de rutas/keys, compartida por el disco local y S3.

`main.py` y `pipeline.py` escriben en disco local bajo estas mismas rutas
relativas a `settings.data_dir`; `_sync_job_to_storage` (main.py) sube cada
archivo a S3 usando esa misma ruta relativa como key. Centralizar la
convención acá evita que ambos lados diverjan silenciosamente.
"""

from __future__ import annotations


def upload_original_dir(job_id: str) -> str:
    return f"uploads/{job_id}/original"


def upload_processed_dir(job_id: str) -> str:
    return f"uploads/{job_id}/processed"


def catalog_dir(job_id: str) -> str:
    return f"catalogs/{job_id}"


def background_key(name: str) -> str:
    return f"backgrounds/{name}"


def job_state_key(job_id: str) -> str:
    return f"jobs/{job_id}.json"
