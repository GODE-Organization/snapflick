.PHONY: help install dev test lint catalog docker-build docker-build-push docker-run warmup web

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install:  ## Instala dependencias del agente
	cd agent && pip install -e ".[dev]"

dev:      ## Levanta la API en http://localhost:8080
	cd agent && uvicorn snapflick.main:app --reload --host 0.0.0.0 --port 8080

test:     ## Corre los tests
	cd agent && pytest -q

lint:     ## Formatea y revisa
	cd agent && ruff check --fix src tests && ruff format src tests

catalog:  ## Procesa samples/input y genera el catálogo
	cd agent && python -m snapflick.cli ../samples/input \
		--background ../samples/backgrounds/marca.jpg --out ../samples/output

docker-build:  ## Construye la imagen local (arquitectura del host, para dev/test)
	docker buildx build --platform linux/amd64 --load -t snapflick:local ./agent

docker-build-push:  ## Construye y publica la imagen multi-arch (amd64+arm64) en un solo push
	@test -n "$(IMAGE_URI)" || (echo "Uso: make docker-build-push IMAGE_URI=<cuenta>.dkr.ecr.<region>.amazonaws.com/snapflick:latest"; exit 1)
	docker buildx build --platform linux/amd64,linux/arm64 -t $(IMAGE_URI) --push ./agent

docker-run:    ## Corre el contenedor local
	docker run --rm -p 8080:8080 --env-file agent/.env snapflick:local

warmup:   ## Calienta rembg y el proveedor de IA antes de grabar una demo
	curl -X POST $${SNAPFLICK_URL:-http://localhost:8080}/warmup

web:      ## Levanta el frontend
	cd web && npm run dev
