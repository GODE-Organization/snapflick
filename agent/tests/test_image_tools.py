from pathlib import Path

from PIL import Image, ImageDraw

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


def test_compose_no_pinta_caja_negra_en_el_bounding_box(tmp_path: Path):
    """Regresión: la sombra debe tener la forma del producto, no ser un
    rectángulo opaco del tamaño del bounding box del recorte (bug del
    `paste` sin máscara: la "L" del alfa se convertía a RGBA opaca y pegaba
    una caja negra en todo el bounding box)."""
    from snapflick.config import settings

    # Recorte del tamaño del canvas para que sí se reescale y quede centrado
    # de forma predecible; elipse inscrita => las esquinas son transparentes.
    n = settings.canvas_size
    cutout = tmp_path / "c.png"
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, n - 1, n - 1), fill=(0, 180, 0, 255))
    img.save(cutout)

    out = compose_on_background(str(cutout), None, str(tmp_path / "o.jpg"))
    result = Image.open(out).convert("RGB")

    usable = int(n * (1 - 2 * settings.product_margin))
    off = (n - usable) // 2  # esquina del bounding box del producto reescalado

    # Punto dentro del bounding box pero fuera de la elipse (transparente en el
    # recorte): en el resultado debe seguir casi blanco, no ennegrecido.
    px = (off + int(usable * 0.04), off + int(usable * 0.04))
    r, g, b = result.getpixel(px)
    assert min(r, g, b) > 170, f"esquina oscura {(r, g, b)} en {px}: la sombra tapó el bounding box"
