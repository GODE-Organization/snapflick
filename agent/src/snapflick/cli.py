"""CLI para desarrollo: procesa una carpeta y genera el catálogo.

python -m snapflick.cli samples/input --background samples/backgrounds/marca.jpg
"""

from __future__ import annotations

import argparse
import logging
import uuid
from pathlib import Path

from .config import settings
from .models.schemas import Job
from .pipeline import run_job

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera un catálogo desde una carpeta de fotos")
    ap.add_argument("folder", help="Carpeta con las fotos de producto")
    ap.add_argument("--background", default=None, help="Imagen de fondo de marca")
    ap.add_argument("--out", default=None, help="Carpeta de salida")
    args = ap.parse_args()

    logging.basicConfig(level=settings.log_level)
    images = sorted(str(p) for p in Path(args.folder).iterdir() if p.suffix.lower() in EXT)
    if not images:
        raise SystemExit(f"No se encontraron imágenes en {args.folder}")

    job = Job(id=uuid.uuid4().hex[:12], total_images=len(images))
    run_job(job, images, args.background, workdir=Path(args.out) if args.out else None)
    print(f"\nEstado: {job.status.value}  ·  {len(job.products)}/{job.total_images} productos")
    if job.plan:
        print(f"Catálogo: {job.plan.catalog_title}")
        print(f"Categorías: {', '.join(job.plan.categories)}")
    print(f"HTML: {job.catalog_html_path}")
    print(f"PDF: {job.catalog_pdf_path}")
    for e in job.errors:
        print(f"  ! {e}")


if __name__ == "__main__":
    main()
