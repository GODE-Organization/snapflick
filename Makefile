.PHONY: help install dev test lint catalog docker-build docker-run web

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

docker-build:  ## Construye la imagen ARM64
	docker buildx build --platform linux/arm64 -t snapflick:local ./agent

docker-run:    ## Corre el contenedor local
	docker run --rm -p 8080:8080 --env-file agent/.env snapflick:local

web:      ## Levanta el frontend
	cd web && npm run dev
