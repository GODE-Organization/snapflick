"""Corre el pipeline de imagen de punta a punta, sin tocar Bedrock.

remove_background/compose_on_background/make_thumbnail SÍ se ejecutan de verdad
(rembg + Pillow, todo local). Lo único que no se prueba aquí es VisionAgent /
CatalogAgent (eso requiere credenciales de Bedrock — ver docs/03-revision-tecnica.md).

Se salta en CI porque la primera llamada a rembg descarga el modelo ONNX
(~176 MB) desde GitHub Releases; en la máquina de cada desarrollador se
descarga una sola vez y queda cacheado en `~/.u2net` (o `U2NET_HOME`), así que
localmente esta prueba sí corre y confirma el pipeline real.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from snapflick.config import settings
from snapflick.tools.image_tools import compose_on_background, make_thumbnail, remove_background

pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="descarga el modelo de rembg (~176MB) la primera vez; se corre localmente",
)


def _make_synthetic_photo(path: Path) -> None:
    img = Image.new("RGB", (300, 300), (245, 245, 245))
    # un "producto" simple y contrastado en el centro
    for x in range(90, 210):
        for y in range(90, 210):
            img.putpixel((x, y), (200, 30, 30))
    img.save(path, "JPEG")


def test_pipeline_de_imagen_corre_de_punta_a_punta(tmp_path: Path):
    src = tmp_path / "foto_original.jpg"
    _make_synthetic_photo(src)

    cutout_path = remove_background(str(src), str(tmp_path / "cutout.png"))
    assert Path(cutout_path).exists()
    cutout_img = Image.open(cutout_path)
    assert cutout_img.mode == "RGBA"

    composed_path = compose_on_background(cutout_path, None, str(tmp_path / "compuesto.jpg"))
    assert Path(composed_path).exists()
    composed_img = Image.open(composed_path)
    assert composed_img.mode == "RGB"
    assert composed_img.size == (settings.canvas_size, settings.canvas_size)

    thumb_path = make_thumbnail(composed_path, str(tmp_path / "thumb.jpg"))
    assert Path(thumb_path).exists()
    thumb_img = Image.open(thumb_path)
    assert max(thumb_img.size) == settings.thumbnail_size
