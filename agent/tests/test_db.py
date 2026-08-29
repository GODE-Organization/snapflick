"""JobStore: guardar y recuperar Jobs de SQLite, incluida la sobreescritura."""

from __future__ import annotations

from pathlib import Path

from snapflick.db import JobStore
from snapflick.models.schemas import Job, JobStatus


def test_save_and_get_roundtrip(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    job = Job(id="job-1", total_images=3)

    store.save(job)
    loaded = store.get("job-1")

    assert loaded is not None
    assert loaded.id == job.id
    assert loaded.status == JobStatus.PENDING
    assert loaded.total_images == 3


def test_save_overwrites_existing_row(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    job = Job(id="job-1", total_images=1)
    store.save(job)

    job.status = JobStatus.DONE
    job.processed_images = 1
    store.save(job)

    loaded = store.get("job-1")
    assert loaded is not None
    assert loaded.status == JobStatus.DONE
    assert loaded.processed_images == 1
    assert len(store.all()) == 1


def test_get_missing_returns_none(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    assert store.get("does-not-exist") is None


def test_all_survives_reopening_the_store(tmp_path: Path):
    """Simula un reinicio del proceso: un JobStore nuevo apuntando al mismo
    archivo debe ver los jobs guardados por una instancia anterior."""
    db_path = tmp_path / "jobs.db"
    JobStore(db_path).save(Job(id="job-1", total_images=1))

    reopened = JobStore(db_path)
    jobs = reopened.all()

    assert len(jobs) == 1
    assert jobs[0].id == "job-1"
