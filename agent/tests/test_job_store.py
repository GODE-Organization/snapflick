"""JobStateStore: SqliteJobStore delega en db.JobStore; S3JobStore usa un JSON
por job bajo jobs/<id>.json, con un cliente S3 falso (sin credenciales/red)."""

from __future__ import annotations

import json
from pathlib import Path

from snapflick.job_store import S3JobStore, SqliteJobStore, get_job_store
from snapflick.models.schemas import Job, JobStatus


def test_sqlite_job_store_roundtrip(tmp_path: Path):
    store = SqliteJobStore(tmp_path / "jobs.db")
    job = Job(id="job-1", total_images=2)

    store.save(job)
    loaded = store.get("job-1")

    assert loaded is not None
    assert loaded.id == "job-1"
    assert store.all() == [loaded]


class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakePaginator:
    def __init__(self, client: _FakeS3Client):
        self._client = client

    def paginate(self, Bucket, Prefix):  # noqa: N803 (nombres de boto3)
        keys = [k for k in self._client.objects if k.startswith(Prefix)]
        yield {"Contents": [{"Key": k} for k in keys]}


class _FakeS3Client:
    """Doble mínimo de un cliente boto3 S3: put_object/get_object/list_objects_v2
    contra un dict en memoria, suficiente para probar S3JobStore sin red."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):  # noqa: N803
        from botocore.exceptions import ClientError

        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "GetObject")
        return {"Body": _FakeBody(self.objects[Key])}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return _FakePaginator(self)


def _fake_job_store(monkeypatch) -> S3JobStore:
    fake_client = _FakeS3Client()

    def _fake_init(self, bucket, region):
        self.bucket = bucket
        self.client = fake_client

    monkeypatch.setattr("snapflick.job_store.S3JobStore.__init__", _fake_init)
    return S3JobStore("fake-bucket", "us-east-1")


def test_s3_job_store_roundtrip(monkeypatch):
    store = _fake_job_store(monkeypatch)
    job = Job(id="job-s3", total_images=1)

    store.save(job)
    loaded = store.get("job-s3")

    assert loaded is not None
    assert loaded.id == "job-s3"
    assert store.client.objects["jobs/job-s3.json"] == job.model_dump_json().encode("utf-8")


def test_s3_job_store_get_missing_returns_none(monkeypatch):
    store = _fake_job_store(monkeypatch)
    assert store.get("does-not-exist") is None


def test_s3_job_store_all_lists_only_under_jobs_prefix(monkeypatch):
    store = _fake_job_store(monkeypatch)
    store.save(Job(id="job-a", total_images=1))
    store.save(Job(id="job-b", total_images=1))
    store.client.objects["backgrounds/marca.jpg"] = b"not-a-job"

    jobs = store.all()

    assert {j.id for j in jobs} == {"job-a", "job-b"}


def test_get_job_store_uses_s3_when_bucket_set(monkeypatch):
    import snapflick.job_store as job_store_module

    monkeypatch.setattr(job_store_module.settings, "s3_bucket", "some-bucket")
    monkeypatch.setattr(job_store_module.settings, "aws_region", "us-east-1")
    monkeypatch.setattr(
        job_store_module.S3JobStore,
        "__init__",
        lambda self, bucket, region: None,
    )

    assert isinstance(get_job_store(), S3JobStore)


def test_get_job_store_uses_sqlite_when_no_bucket(monkeypatch, tmp_path):
    import snapflick.job_store as job_store_module

    monkeypatch.setattr(job_store_module.settings, "s3_bucket", None)
    monkeypatch.setattr(job_store_module.settings, "data_dir", tmp_path)

    assert isinstance(get_job_store(), SqliteJobStore)


def test_status_persists_across_save(monkeypatch):
    store = _fake_job_store(monkeypatch)
    job = Job(id="job-status", total_images=1)
    store.save(job)

    job.status = JobStatus.DONE
    job.processed_images = 1
    store.save(job)

    reloaded = json.loads(store.client.objects["jobs/job-status.json"])
    assert reloaded["status"] == "done"
