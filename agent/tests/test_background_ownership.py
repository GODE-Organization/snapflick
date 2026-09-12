"""Los fondos de marca (`/backgrounds`) ahora se asocian a la cookie de sesión
que los subió (ver `session_dependency` en main.py) — antes eran un pool
totalmente compartido, así que en incógnito (sesión distinta) cualquiera veía
los fondos subidos por otra persona. `_require_background_owner` reproduce la
misma regla que `_require_owner` para jobs: fondos sin dueño (legacy) o
marcados "Por defecto" siguen siendo de acceso libre."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

from fastapi import HTTPException, UploadFile

import snapflick.main as main_module


def _setup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main_module.settings, "data_dir", tmp_path)
    monkeypatch.setattr(main_module, "DATA", tmp_path)
    # Sin esto, un `.env` de dev con SNAPFLICK_S3_BUCKET real haría que
    # get_storage() devuelva S3Storage y el test liste/borre fondos contra el
    # bucket de verdad en vez de aislarse en tmp_path.
    monkeypatch.setattr(main_module.settings, "s3_bucket", None)


def _upload(filename: str, session_id: str) -> dict:
    upload = UploadFile(filename=filename, file=io.BytesIO(b"fake-image-bytes"))
    return asyncio.run(main_module.upload_background(file=upload, session_id=session_id))


def test_list_backgrounds_no_muestra_fondos_de_otra_sesion(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    bg_a = _upload("playa.jpg", "session-a")
    bg_b = _upload("oficina.jpg", "session-b")

    keys_a = {b["background_key"] for b in main_module.list_backgrounds(session_id="session-a")}
    keys_b = {b["background_key"] for b in main_module.list_backgrounds(session_id="session-b")}

    assert bg_a["background_key"] in keys_a
    assert bg_b["background_key"] not in keys_a
    assert bg_b["background_key"] in keys_b
    assert bg_a["background_key"] not in keys_b


def test_upload_background_no_filtra_el_nombre_de_archivo_original(tmp_path: Path, monkeypatch):
    """`background_key` debe ser un código opaco, igual que `ProductRecord.id`
    — no el nombre de archivo original, que a veces contiene información del
    autor/origen de la imagen (ver `alper-guzeler-...unsplash.jpg` en el caso
    real que motivó este cambio)."""
    _setup(tmp_path, monkeypatch)

    uploaded = _upload("alper-guzeler-secret-name.jpg", "session-a")

    assert "alper-guzeler-secret-name" not in uploaded["background_key"]
    assert uploaded["background_key"].endswith(".jpg")


def test_list_backgrounds_muestra_fondos_legacy_sin_dueño(tmp_path: Path, monkeypatch):
    """Un fondo escrito directamente a disco (como los subidos antes de que
    `upload_background` registrara dueño) no tiene entrada en el mapa de
    owners — debe seguir viéndose para cualquiera, igual que un job con
    `session_id=None`."""
    _setup(tmp_path, monkeypatch)

    legacy_dir = tmp_path / "backgrounds"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "legacy_bg.jpg").write_bytes(b"old-file")

    keys = {b["background_key"] for b in main_module.list_backgrounds(session_id="session-a")}
    assert "legacy_bg.jpg" in keys


def test_list_backgrounds_muestra_el_fondo_por_defecto_a_cualquiera(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    uploaded = _upload("marca.jpg", "session-a")
    main_module._set_default_background_key(uploaded["background_key"])

    keys_b = {b["background_key"] for b in main_module.list_backgrounds(session_id="session-b")}
    assert uploaded["background_key"] in keys_b


def test_require_background_owner_rechaza_fondo_de_otra_sesion(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    uploaded = _upload("privado.jpg", "session-a")

    try:
        main_module._require_background_owner(uploaded["background_key"], "session-b")
        raise AssertionError("debía lanzar HTTPException 404")
    except HTTPException as exc:
        assert exc.status_code == 404


def test_require_background_owner_permite_al_dueño_y_a_fondos_legacy(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    uploaded = _upload("propio.jpg", "session-a")

    main_module._require_background_owner(uploaded["background_key"], "session-a")
    main_module._require_background_owner("legacy_bg_sin_registrar.jpg", "session-a")


def test_delete_background_rechaza_fondo_de_otra_sesion(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    uploaded = _upload("privado.jpg", "session-a")

    try:
        main_module.delete_background(uploaded["background_key"], session_id="session-b")
        raise AssertionError("debía lanzar HTTPException 404")
    except HTTPException as exc:
        assert exc.status_code == 404
    # y el archivo no debe haberse borrado
    assert (tmp_path / "backgrounds" / uploaded["background_key"]).exists()


def test_delete_background_permite_al_dueño_y_borra_el_archivo(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    uploaded = _upload("propio.jpg", "session-a")
    key = uploaded["background_key"]

    result = main_module.delete_background(key, session_id="session-a")

    assert result == {"background_key": key, "deleted": True}
    assert not (tmp_path / "backgrounds" / key).exists()
    assert key not in main_module._get_background_owners()


def test_delete_background_permite_borrar_un_fondo_legacy_sin_dueño(tmp_path: Path, monkeypatch):
    """Es exactamente el caso que motivó este endpoint: un fondo subido antes
    de que existiera el registro de dueño quedó público en producción y no
    había forma de borrarlo — debe poder borrarlo cualquier sesión."""
    _setup(tmp_path, monkeypatch)
    legacy_dir = tmp_path / "backgrounds"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "legacy_bg.jpg").write_bytes(b"old-file")

    result = main_module.delete_background("legacy_bg.jpg", session_id="cualquier-sesion")

    assert result == {"background_key": "legacy_bg.jpg", "deleted": True}
    assert not (legacy_dir / "legacy_bg.jpg").exists()


def test_delete_background_404_si_no_existe(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)

    try:
        main_module.delete_background("no-existe.jpg", session_id="session-a")
        raise AssertionError("debía lanzar HTTPException 404")
    except HTTPException as exc:
        assert exc.status_code == 404


def test_delete_background_desmarca_el_fondo_por_defecto(tmp_path: Path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    uploaded = _upload("marca.jpg", "session-a")
    key = uploaded["background_key"]
    main_module._set_default_background_key(key)

    main_module.delete_background(key, session_id="session-a")

    assert main_module._get_default_background_key() is None
