# AgentCore Runtime exige ARM64. Construir con:
#   docker buildx build --platform linux/arm64 -t snapflick .
FROM --platform=linux/arm64 python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    U2NET_HOME=/opt/rembg

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Hornea el modelo de rembg en la imagen para que no se descargue en el primer
# request (y se caiga por timeout). Se descarga con pooch en vez de con
# `rembg.new_session(...)` porque importar `rembg`/`onnxruntime` revienta con
# SIGSEGV bajo emulación QEMU al hacer `docker buildx --platform linux/arm64`
# desde un host x86/amd64 — ver docs/03-revision-tecnica.md, hallazgo #8.
RUN python -c "\
import pooch; \
pooch.retrieve( \
    'https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx', \
    'md5:fc16ebd8b0c10d971d3513d564d01e29', \
    fname='isnet-general-use.onnx', \
    path='/opt/rembg', \
)"

EXPOSE 8080
CMD ["uvicorn", "snapflick.main:app", "--host", "0.0.0.0", "--port", "8080"]
