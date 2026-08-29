"""with_retry: reintenta solo errores de límite de tasa, con espera exponencial."""

from __future__ import annotations

import pytest

from snapflick import retry as retry_module
from snapflick.retry import with_retry


class _RateLimited(Exception):
    status_code = 429


class _NotFound(Exception):
    status_code = 404


def test_reintenta_hasta_que_la_funcion_funciona(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(retry_module.time, "sleep", lambda s: sleeps.append(s))

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _RateLimited("saturado")
        return "ok"

    result = with_retry(flaky, max_attempts=5, base_delay=1.0)

    assert result == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2  # dos reintentos antes de éxito
    assert sleeps[0] < sleeps[1]  # espera exponencial, creciente


def test_no_reintenta_errores_que_no_son_de_limite_de_tasa(monkeypatch):
    monkeypatch.setattr(retry_module.time, "sleep", lambda s: pytest.fail("no debería dormir"))

    def always_404():
        raise _NotFound("no existe")

    with pytest.raises(_NotFound):
        with_retry(always_404, max_attempts=5)


def test_propaga_despues_de_agotar_los_intentos(monkeypatch):
    monkeypatch.setattr(retry_module.time, "sleep", lambda s: None)

    def always_rate_limited():
        raise _RateLimited("saturado")

    with pytest.raises(_RateLimited):
        with_retry(always_rate_limited, max_attempts=3)
