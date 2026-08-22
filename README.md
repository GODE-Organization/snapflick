# SnapFlick

**Fotos caseras de productos → catálogo publicable, en minutos.**

Un agente construido con [Strands Agents SDK](https://strandsagents.com) y Amazon Bedrock
que toma las fotos que una bodega o un emprendedor saca con el celular, les quita el fondo,
las compone sobre el fondo de marca del negocio, lee el empaque para extraer los datos del
producto y arma un catálogo agrupado por categoría, listo para publicar.

---

## El problema

Una tienda con 200 referencias no puede pagar un fotógrafo ni un catalogador. Sus fotos
salen sobre la mesa de la cocina, con fondos distintos y sin datos estructurados. El
resultado es que nunca publican catálogo, o publican uno que se ve improvisado.

## Qué hace SnapFlick

1. **Recorta** el producto y elimina el fondo (`rembg`, local, sin costo por imagen).
2. **Compone** el producto sobre el fondo de marca que el usuario guardó una sola vez.
3. **Lee el empaque** con un modelo multimodal de Amazon Bedrock y extrae nombre, marca,
   presentación, descripción, ingredientes y código de barras — **sin inventar nada**:
   lo que no se ve queda en `null` y marcado para revisión.
4. **Categoriza el lote completo de una vez**, de modo que no salgan "Bebida", "Bebidas"
   y "Refrescos" como tres categorías distintas.
5. **Genera** el catálogo en HTML navegable (autocontenido, con las imágenes incrustadas)
   y JSON exportable.

---

## Arquitectura

Ver [`docs/00-arquitectura.md`](docs/00-arquitectura.md) y el diagrama en
[`docs/architecture.mermaid`](docs/architecture.mermaid).

Dos agentes especializados coordinados por el pipeline (`pipeline.py`):

| Agente | Responsabilidad |
|---|---|
| `VisionAgent` | Lee el empaque y devuelve una `ProductSheet` validada (salida estructurada) |
| `CatalogAgent` | Asigna categorías coherentes a todo el lote y arma el plan del catálogo |

El pipeline (no un tercer agente) coordina el flujo y aísla los fallos por imagen — ver
`docs/03-revision-tecnica.md` para el razonamiento detrás de esta decisión.

Las herramientas de imagen (`rembg`, Pillow) son determinísticas y no consumen modelo; se
llaman directo desde el pipeline, no como `tools` de un agente.

Un único servidor **FastAPI** (`snapflick.main:app`) expone tanto el contrato que exige
Amazon Bedrock AgentCore (`POST /invocations`, `GET /ping` en :8080) como la API propia del
producto (`/jobs`, `/backgrounds`, `/files`).

---

## Puesta en marcha desde cero

Pensado para clonar el repo en Windows, Linux o macOS y tener el agente corriendo en
menos de 15 minutos, sin experiencia previa en el proyecto.

### 0. Requisitos previos

- **Python 3.11** (no 3.10, no 3.12 — el proyecto se fija a 3.11 porque es lo que soportan
  las ruedas de `onnxruntime`/`rembg` que usamos; ver
  [`docs/03-revision-tecnica.md`](docs/03-revision-tecnica.md)).
- **Git**.
- **Docker Desktop** (solo si vas a construir el contenedor — no hace falta para desarrollar
  ni correr los tests).
- Credenciales de AWS con acceso a un modelo Claude con visión en Amazon Bedrock, **solo**
  si vas a usar el `VisionAgent`/`CatalogAgent` de verdad. Todo lo demás (recorte de imagen,
  API, tests) funciona sin AWS.

Verifica tu versión de Python antes de continuar:

```bash
python3 --version   # macOS / Linux — debe imprimir 3.11.x
py -3.11 --version  # Windows (si tienes varias versiones instaladas con el launcher py)
```

Si no tienes Python 3.11 instalado:
- **Windows**: `winget install Python.Python.3.11` o descárgalo de python.org.
- **macOS**: `brew install python@3.11`.
- **Linux (Debian/Ubuntu)**: `sudo apt install python3.11 python3.11-venv`.

### 1. Clonar y entrar al proyecto

```bash
git clone <url-del-repo> snapflick
cd snapflick
```

### 2. Crear el entorno virtual y activarlo

**macOS / Linux (bash o zsh):**
```bash
cd agent
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
cd agent
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```
Si PowerShell bloquea el script de activación con un error de política de ejecución, corre
una vez (como el propio usuario, no como administrador):
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Windows (Git Bash):**
```bash
cd agent
py -3.11 -m venv .venv
source .venv/Scripts/activate
```

A partir de aquí los comandos son los mismos en las tres plataformas, con el entorno virtual
activado (verás `(.venv)` al inicio de la línea de comandos).

### 3. Instalar dependencias

Desde la raíz del repo (recomendado, usa el `Makefile`):
```bash
make install
```

O manualmente, si `make` no está disponible (p. ej. Windows sin Git Bash/WSL):
```bash
cd agent
pip install -e ".[dev]"
```

La primera instalación tarda un par de minutos porque `rembg` trae `scipy` y
`scikit-image`. Es normal.

### 4. Configurar variables de entorno

```bash
cp agent/.env.example agent/.env
```
En Windows PowerShell, si `cp` no existe: `Copy-Item agent\.env.example agent\.env`.

Abre `agent/.env` y ajusta al menos:
- `SNAPFLICK_AWS_REGION` — región donde tienes acceso a Bedrock (recomendado `us-east-1`).
- `SNAPFLICK_BEDROCK_MODEL_ID` — el ID del modelo con visión habilitado en tu cuenta.

Si aún no tienes acceso a Bedrock configurado, puedes seguir los pasos 5-7 igual: no hacen
falta credenciales de AWS para instalar, correr los tests o levantar la API — solo para que
`VisionAgent`/`CatalogAgent` respondan de verdad.

### 5. Correr los tests

```bash
make test
# o directamente:
cd agent && pytest -q
```

Estos tests **no** llaman a Bedrock ni descargan el modelo de `rembg` — usan imágenes
sintéticas generadas en memoria y un doble de prueba (mock) para los agentes. Deben pasar en
cualquier máquina, sin AWS y sin conexión a internet.

### 6. Levantar la API en local

```bash
make dev
```
Abre `http://localhost:8080/docs` para ver la API interactiva (Swagger UI), o prueba:
```bash
curl http://localhost:8080/ping
```

### 7. Procesar un lote de prueba por CLI (sin frontend)

Coloca unas fotos en `samples/input/` (y opcionalmente un fondo de marca en
`samples/backgrounds/`), luego:
```bash
make catalog
```
El resultado queda en `samples/output/catalogo.html` — ábrelo con doble clic en tu
navegador, las imágenes están incrustadas en el propio archivo.

> **Nota:** este paso sí necesita credenciales de AWS válidas y acceso al modelo de Bedrock
> configurado en el paso 4, porque `VisionAgent`/`CatalogAgent` invocan el modelo de verdad.

### 8. (Opcional) Frontend

El frontend en `web/` todavía es un scaffold mínimo — ver
[`web/README.md`](web/README.md) para el plan de inicialización con Next.js.
```bash
make web   # una vez que web/ tenga el proyecto Next.js inicializado
```

### Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `pip install` falla instalando `onnxruntime`/`rembg` | Python distinto de 3.11, o CPU/OS sin rueda precompilada | Confirma `python --version` dentro del venv activado |
| `ModuleNotFoundError: snapflick` | El venv no está activado, o se instaló sin `-e` | Repite el paso 2 y 3 en orden |
| La API arranca pero `/jobs` falla al extraer datos | Sin credenciales AWS o sin acceso al modelo en Bedrock | Revisa `agent/.env` y sigue `docs/02-guia-despliegue-aws.md` |
| `agent/.env` no se está leyendo | El proceso no se lanzó desde `agent/` o el archivo no se llama exactamente `.env` | Confirma la ruta con `cat agent/.env` (o `Get-Content agent\.env` en PowerShell) |

---

## Cómo desplegarlo

```bash
make docker-build   # imagen ARM64
```

El contenedor ya implementa el contrato completo de Amazon Bedrock AgentCore
(`POST /invocations`, `GET /ping`, puerto 8080, ARM64) directamente en `main.py` — no hace
falta ningún entrypoint adicional. El despliegue a AgentCore Runtime se hace registrando esa
misma imagen (ver `docs/02-guia-despliegue-aws.md`, sección "Camino A"). Si construyes la
imagen ARM64 con `docker buildx` desde un host x86/amd64, ver `docs/03-revision-tecnica.md`
(hallazgo #8) sobre un problema conocido de `onnxruntime` bajo emulación QEMU y cómo se
evita.

Plan B documentado con AWS App Runner (mismo contenedor, sin cambios de código).

---

## Estructura del repositorio

```
snapflick/
├── agent/                       servicio Python (Strands + FastAPI)
│   ├── src/snapflick/
│   │   ├── agents/              VisionAgent, CatalogAgent
│   │   ├── tools/               imagen y catálogo (deterministas, sin modelo)
│   │   ├── models/schemas.py    contrato de datos compartido
│   │   ├── pipeline.py          orquestación del job
│   │   ├── main.py              API FastAPI (/invocations, /ping, /jobs)
│   │   └── cli.py               procesar una carpeta desde consola
│   ├── tests/
│   └── Dockerfile               ARM64, con el modelo de rembg horneado
├── web/                         frontend Next.js
├── infra/                       CloudFormation y scripts de despliegue
├── docs/                        arquitectura, alcance, despliegue, revisión técnica
└── samples/                     fotos de ejemplo y fondos de marca
```

## Documentación del proyecto

- [Arquitectura y decisiones de diseño](docs/00-arquitectura.md)
- [Alcance del producto](docs/01-alcance-del-producto.md)
- [Guía de despliegue en AWS](docs/02-guia-despliegue-aws.md)
- [Revisión técnica del scaffolding](docs/03-revision-tecnica.md)

## Licencia

MIT — ver [LICENSE](LICENSE).
