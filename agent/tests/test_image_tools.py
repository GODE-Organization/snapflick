from pathlib import Path

from PIL import Image

from snapflick.tools.image_tools import _autocrop_alpha, _cover_resize, compose_on_background


def test_autocrop_alpha_recorta_al_contenido():
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (40, 40), (255, 0, 0, 255)), (80, 80))
    out = _autocrop_alpha(img, pad=0)
    assert out.size == (40, 40)


def test_cover_resize_devuelve_tamano_exacto():
    out = _cover_resize(Image.new("RGB", (800, 400)), 300, 300)
    assert out.size == (300, 300)


def test_compose_genera_jpg(tmp_path: Path):
    cutout = tmp_path / "c.png"
    Image.new("RGBA", (100, 100), (0, 200, 0, 255)).save(cutout)
    out = compose_on_background(str(cutout), None, str(tmp_path / "o.jpg"))
    assert Path(out).exists()
    assert Image.open(out).mode == "RGB"
