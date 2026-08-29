# Imagen multi-arquitectura (linux/amd64 + linux/arm64) desde un único build.
# amd64 es lo que corre en ECS Express Mode/App Runner; arm64 es lo que exige
# Bedrock AgentCore Runtime si además se registra ahí (ver docs/02). El base
# image ya publica manifiestos para ambas arquitecturas, así que no hace falta
# fijar --platform acá: buildx decide el target por invocación (ver Makefile /
# infra/scripts/deploy.sh):
#   docker buildx build --platform linux/amd64,linux/arm64 -t snapflick --push .
FROM python:3.11-slim-bookworm

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
# SIGSEGV bajo emulación QEMU al construir para una arquitectura distinta a la
# del host (p.ej. arm64 desde un host x86/amd64) — ver docs/03-revision-tecnica.md,
# hallazgo #8. `pooch.retrieve` no importa `onnxruntime`, así que este paso es
# seguro bajo QEMU para CUALQUIER arquitectura destino, lo que es lo que hace
# posible construir esta imagen como multi-arch en un único build — la sesión
# real de onnxruntime recién se crea en tiempo de ejecución, dentro del
# contenedor ya construido para su arquitectura nativa, nunca bajo emulación.
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
