"""Herramientas de imagen. Sin IA: Pillow + rembg, todo local y gratis.

Son deterministas (recortar, componer, miniaturizar siempre en el mismo orden),
así que se llaman directo desde el pipeline como funciones normales. No se
exponen como @tool de Strands: ningún agente decide cuándo invocarlas, así que
envolverlas como tool solo añadiría un import sin uso real.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageFilter

from ..config import settings

_session = None


def _get_session():
    """Carga perezosa del modelo rembg. Se hornea en la imagen Docker en build."""
    global _session
    if _session is None:
        from rembg import new_session

        _session = new_session(settings.rembg_model)
    return _session


def remove_background(image_path: str, output_path: str) -> str:
    """Quita el fondo de una foto de producto y devuelve un PNG con transparencia.

    Args:
        image_path: ruta de la foto original.
        output_path: ruta destino del PNG recortado.
    """
    from rembg import remove

    src = Path(image_path).read_bytes()
    out = remove(src, session=_get_session())
    img = Image.open(io.BytesIO(out)).convert("RGBA")
    img = _autocrop_alpha(img)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def _autocrop_alpha(img: Image.Image, pad: int = 8, alpha_threshold: int = 16) -> Image.Image:
    """Recorta al bounding box del canal alfa. Esto es lo que separa un
    resultado profesional de uno casero.

    `getbbox()` cuenta cualquier píxel con alfa > 0 como contenido, pero rembg
    deja restos de alfa casi cero (ruido de 1-30 sobre 255) desparramados
    lejos del producto en algunas fotos. Un solo píxel de ese ruido en una
    esquina infla el bounding box mucho más allá del producto real, y como
    `compose_on_background` centra según este recorte, el producto visible
    termina pegado a un lado en vez de centrado. Umbralizar antes de medir el
    bbox ignora ese ruido sin afectar el borde antialiaseado real del
    producto, que queda pegado al contorno sólido en unos pocos píxeles.
    """
    bbox = img.split()[-1].point(lambda a: 255 if a >= alpha_threshold else 0).getbbox()
    if not bbox:
        return img
    left, top, right, bottom = bbox
    return img.crop(
        (
            max(0, left - pad),
            max(0, top - pad),
            min(img.width, right + pad),
            min(img.height, bottom + pad),
        )
    )


def compose_on_background(cutout_path: str, background_path: str | None, output_path: str) -> str:
    """Compone el producto recortado sobre el fondo de marca del usuario.

    Escala respetando la proporción, centra, deja margen y añade una sombra suave.

    Args:
        cutout_path: PNG con transparencia.
        background_path: imagen de fondo guardada por el usuario. None = fondo blanco.
        output_path: ruta destino del JPG final.
    """
    size = settings.canvas_size
    product = Image.open(cutout_path).convert("RGBA")

    if background_path:
        bg = Image.open(background_path).convert("RGB")
        bg = _cover_resize(bg, size, size)
    else:
        bg = Image.new("RGB", (size, size), (255, 255, 255))

    usable = int(size * (1 - 2 * settings.product_margin))
    product.thumbnail((usable, usable), Image.LANCZOS)

    x = (size - product.width) // 2
    y = (size - product.height) // 2

    # Sombra = silueta del producto en negro, semitransparente y desenfocada.
    # El canal alfa atenuado va como MÁSCARA del paste (no como imagen): sin
    # máscara, Pillow convierte la "L" a RGBA opaca y pega una caja negra del
    # tamaño del bounding box en vez de una sombra con la forma del producto.
    shadow = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    shadow.paste(
        Image.new("RGBA", product.size, (0, 0, 0, 255)),
        (x, y + 12),
        product.split()[-1].point(lambda a: int(a * 0.35)),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(bg.convert("RGBA"), shadow)
    canvas.paste(product, (x, y), product)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, "JPEG", quality=92)
    return output_path


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    ratio = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    left = (img.width - w) // 2
    top = (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def keep_original(image_path: str, output_path: str) -> str:
    """Recodifica la foto tal cual a JPG, sin quitar ni componer fondo.

    Usado cuando el usuario elige "mantener el fondo original" para un
    producto: se salta rembg y `compose_on_background` por completo (no solo
    porque el resultado no lo necesita, sino porque no tiene sentido gastar
    tiempo/cuota removiendo un fondo que se va a descartar).
    """
    img = Image.open(image_path).convert("RGB")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=92)
    return output_path


def make_thumbnail(image_path: str, output_path: str) -> str:
    """Genera una miniatura cuadrada para la vista de galería."""
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((settings.thumbnail_size, settings.thumbnail_size), Image.LANCZOS)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=85)
    return output_path
