"""LocalStorage.delete_prefix: usado por `DELETE /jobs/{id}` para borrar
todos los artefactos de un job (uploads/, catalogs/) sin tocar backgrounds/,
que es un pool compartido entre jobs."""

from __future__ import annotations

from pathlib import Path

from snapflick.tools.storage_tools import LocalStorage


def test_delete_prefix_borra_el_directorio(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    (tmp_path / "uploads" / "job-1" / "original").mkdir(parents=True)
    (tmp_path / "uploads" / "job-1" / "original" / "foto.jpg").write_bytes(b"x")
    (tmp_path / "uploads" / "job-2" / "original").mkdir(parents=True)
    (tmp_path / "uploads" / "job-2" / "original" / "foto.jpg").write_bytes(b"y")

    storage.delete_prefix("uploads/job-1/")

    assert not (tmp_path / "uploads" / "job-1").exists()
    assert (tmp_path / "uploads" / "job-2" / "original" / "foto.jpg").exists()


def test_delete_prefix_no_falla_si_no_existe(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.delete_prefix("uploads/no-existe/")  # no debe lanzar
