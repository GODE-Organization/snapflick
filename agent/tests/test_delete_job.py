"""`DELETE /jobs/{job_id}`: borra el registro (STORE) y los artefactos en
disco (uploads/, catalogs/), pero nunca backgrounds/ (pool compartido)."""

from __future__ import annotations

from pathlib import Path

import snapflick.main as main_module
from snapflick.db import JobStore
from snapflick.models.schemas import Job, JobStatus


def _setup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(main_module, "STORE", JobStore(tmp_path / "jobs.db"))
    # Sin esto, un `.env` de dev con SNAPFLICK_S3_BUCKET real haría que
    # get_storage() devuelva S3Storage y el test borre/liste contra el bucket
    # de verdad en vez de aislarse en tmp_path.
    monkeypatch.setattr(main_module.settings, "s3_bucket", None)


def test_delete_job_borra_registro_y_artefactos(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    job_id = "job-to-delete"
    job = Job(id=job_id, status=JobStatus.DONE, total_images=1, processed_images=1)
    main_module.JOBS[job_id] = job
    main_module.STORE.save(job)

    upload_dir = tmp_path / "uploads" / job_id / "original"
    upload_dir.mkdir(parents=True)
    (upload_dir / "foto.jpg").write_bytes(b"fake")
    catalog_dir = tmp_path / "catalogs" / job_id
    catalog_dir.mkdir(parents=True)
    (catalog_dir / "catalogo.html").write_text("<html></html>")

    background_dir = tmp_path / "backgrounds"
    background_dir.mkdir()
    (background_dir / "bg.jpg").write_bytes(b"keep-me")

    result = main_module.delete_job(job_id)

    assert result == {"id": job_id, "deleted": True}
    assert job_id not in main_module.JOBS
    assert main_module.STORE.get(job_id) is None
    assert not (tmp_path / "uploads" / job_id).exists()
    assert not (tmp_path / "catalogs" / job_id).exists()
    assert (background_dir / "bg.jpg").exists()


def test_delete_job_404_si_no_existe(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    from fastapi import HTTPException

    try:
        main_module.delete_job("no-existe")
        raise AssertionError("debía lanzar HTTPException 404")
    except HTTPException as exc:
        assert exc.status_code == 404


def test_delete_job_rechaza_job_en_proceso(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    from fastapi import HTTPException

    job_id = "job-processing"
    job = Job(id=job_id, status=JobStatus.PROCESSING, total_images=2, processed_images=1)
    main_module.JOBS[job_id] = job
    main_module.STORE.save(job)

    try:
        main_module.delete_job(job_id)
        raise AssertionError("debía lanzar HTTPException 400")
    except HTTPException as exc:
        assert exc.status_code == 400
    finally:
        del main_module.JOBS[job_id]
