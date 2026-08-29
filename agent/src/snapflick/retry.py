"""Reintentos con espera exponencial para errores de límite de tasa.

Solo reintenta errores identificados como "límite de tasa" (429 / Gemini
RESOURCE_EXHAUSTED) — cualquier otro error se propaga de inmediato, para que
una imagen genuinamente mala siga fallando rápido dentro del `except` por
imagen que ya tiene `pipeline.run_job` en vez de agotar reintentos en algo que
nunca va a funcionar.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


def _is_rate_limited(exc: Exception) -> bool:
    try:
        from google.genai.errors import APIError as GeminiAPIError
    except ImportError:
        GeminiAPIError = ()  # type: ignore[assignment]

    if isinstance(exc, GeminiAPIError) and exc.status == "RESOURCE_EXHAUSTED":
        return True

    status_code = getattr(exc, "status_code", None)
    return status_code == 429


def with_retry(
    fn: Callable[..., T],
    *args: object,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    **kwargs: object,
) -> T:
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_rate_limited(exc) or attempt == max_attempts - 1:
                raise
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            log.warning(
                "Límite de tasa del proveedor de IA, reintento %d/%d en %.1fs: %s",
                attempt + 1,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
