"""Persistencia de Jobs detrás de una interfaz: SQLite local, S3 en la nube.

Mismo patrón que `tools/storage_tools.py` (`Storage`/`get_storage()`): el
almacenamiento de estado se elige una sola vez según `SNAPFLICK_S3_BUCKET`, sin
que el resto del código sepa cuál backend está usando. `main.py` sigue
llamando `STORE.save(job)`/`STORE.all()` exactamente igual que antes.

Con S3, el disco del contenedor es efímero y puede haber varias instancias
detrás del mismo servicio (App Runner/ECS): SQLite (un archivo local) no
sobrevive un redespliegue ni se comparte entre instancias, así que en ese caso
el estado se guarda como un JSON por job en `jobs/<job_id>.json`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .config import settings
from .db import JobStore as SqliteBackend
from .models.schemas import Job
from .paths import job_state_key


class JobStateStore(ABC):
    @abstractmethod
    def save(self, job: Job) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> Job | None: ...

    @abstractmethod
    def all(self) -> list[Job]: ...

    @abstractmethod
    def delete(self, job_id: str) -> None: ...


class SqliteJobStore(JobStateStore):
    def __init__(self, db_path: str | Path) -> None:
        self._backend = SqliteBackend(db_path)

    def save(self, job: Job) -> None:
        self._backend.save(job)

    def get(self, job_id: str) -> Job | None:
        return self._backend.get(job_id)

    def all(self) -> list[Job]:
        return self._backend.all()

    def delete(self, job_id: str) -> None:
        self._backend.delete(job_id)


class S3JobStore(JobStateStore):
    """Un JSON por job bajo `jobs/<job_id>.json`.

    `all()` lista todos los objetos bajo el prefijo `jobs/` y descarga cada
    uno para poder ordenar por `created_at` — O(n) `get_object` por cada
    llamada a `GET /jobs`. Aceptable a la escala de un demo/hackathon; a
    escala real convendría un índice separado (p.ej. DynamoDB) en vez de
    listar+descargar todo el bucket.
    """

    def __init__(self, bucket: str, region: str):
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def save(self, job: Job) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=job_state_key(job.id),
            Body=job.model_dump_json().encode("utf-8"),
            ContentType="application/json",
        )

    def get(self, job_id: str) -> Job | None:
        from botocore.exceptions import ClientError

        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=job_state_key(job_id))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return None
            raise
        return Job.model_validate_json(obj["Body"].read())

    def all(self) -> list[Job]:
        jobs: list[Job] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix="jobs/"):
            for entry in page.get("Contents", []):
                obj = self.client.get_object(Bucket=self.bucket, Key=entry["Key"])
                jobs.append(Job.model_validate_json(obj["Body"].read()))
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def delete(self, job_id: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=job_state_key(job_id))


def get_job_store() -> JobStateStore:
    if settings.s3_bucket:
        return S3JobStore(settings.s3_bucket, settings.aws_region)
    return SqliteJobStore(Path(settings.data_dir) / "snapflick.db")
