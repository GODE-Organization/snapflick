# SnapFlick

**Fotos caseras de productos → catálogo publicable, en minutos.**

Una aplicación full-stack (agente en Python con [Strands Agents SDK](https://strandsagents.com)
+ FastAPI, frontend en Next.js) que toma las fotos que una bodega o un emprendedor saca con el
celular, les quita el fondo, las compone sobre el fondo de marca del negocio, lee el empaque
para extraer los datos del producto y arma un catálogo agrupado por categoría, listo para
publicar o compartir por un link.

---

## El problema

Una tienda con 200 referencias no puede pagar un fotógrafo ni un catalogador. Sus fotos salen
sobre la mesa de la cocina, con fondos distintos y sin datos estructurados. El resultado es que
nunca publican catálogo, o publican uno que se ve improvisado.

## Qué hace SnapFlick

1. **Recorta** el producto y elimina el fondo (`rembg`, local, sin costo por imagen).
2. **Compone** el producto sobre el fondo de marca que el usuario guardó una sola vez (o lo
   deja tal cual, si prefiere el fondo original de la foto).
3. **Lee el empaque** con un modelo multimodal y extrae nombre, marca, presentación,
   descripción, ingredientes y código de barras — **sin inventar nada**: lo que no se ve queda
   en `null` y marcado para revisión.
4. **Categoriza el lote completo de una vez**, de modo que no salgan "Bebida", "Bebidas" y
   "Refrescos" como tres categorías distintas.
5. **Genera** el catálogo en HTML navegable (autocontenido, con las imágenes incrustadas en
   base64) y JSON exportable, con una vista pública compartible por link (`/c/<job_id>`).
6. Deja **editar** el resultado antes de publicar: nombre, precio, categoría, visibilidad por
   producto, agregar/quitar productos al lote, cambiar el fondo de un producto puntual.

Todo esto detrás de una **sesión anónima por cookie** (sin registro/login): cada visitante solo
ve y edita sus propios jobs; el catálogo público publicado sigue siendo un link abierto para
compartir con quien sea.

---

## Arquitectura

Monorepo con dos partes:

| Carpeta | Qué es |
|---|---|
| `agent/` | Servicio Python — Strands Agents SDK + FastAPI. Un único servidor que implementa tanto el contrato de Amazon Bedrock AgentCore (`POST /invocations`, `GET /ping`) como la API propia del producto. |
| `web/` | Frontend Next.js (App Router, React 19, Tailwind 4). Habla con el backend por HTTP + WebSocket. |

Dos agentes especializados coordinados por un pipeline determinístico (`agent/src/snapflick/pipeline.py`):

| Componente | Responsabilidad |
|---|---|
| `VisionAgent` | Lee el empaque de **una** foto y devuelve una `ProductSheet` validada (salida estructurada de Strands) |
| `CatalogAgent` | Recibe **todo el lote** de una vez y decide categorías coherentes + el plan del catálogo |
| `pipeline.run_job` | No es un tercer agente — es el control de flujo determinístico que orquesta ambos y aísla los fallos por imagen |

Las herramientas de imagen (`rembg`, Pillow, en `tools/image_tools.py`) son deterministas y no
consumen modelo; se llaman directo desde el pipeline, nunca como `@tool` de un agente.

**Cuatro proveedores de modelo intercambiables**, con auto-detección: Amazon Bedrock, Google
Gemini, OpenAI (ChatGPT) y Ollama (local). Sin `SNAPFLICK_MODEL_PROVIDER` fijado, el backend
prueba cada uno en orden hasta que alguno responde y se queda con ese para el resto del
proceso — ver `agent/src/snapflick/model_provider.py`.

**Almacenamiento con el mismo patrón para artefactos y estado de job**: en local, todo vive en
disco (`SNAPFLICK_DATA_DIR`) y en SQLite; con `SNAPFLICK_S3_BUCKET` seteado, las imágenes y el
catálogo se replican a S3 y el estado de cada job se guarda como JSON en S3 en vez de SQLite —
necesario en la nube porque el disco de un contenedor es efímero y puede haber más de una
instancia corriendo. Ver `CLAUDE.md` ("Storage", "Job persistence") para el detalle completo.

Diagrama completo y decisiones de diseño en [`docs/00-arquitectura.md`](docs/00-arquitectura.md)
y [`docs/architecture.mermaid`](docs/architecture.mermaid).

---

## Puesta en marcha desde cero

Pensado para clonar el repo en Windows, Linux o macOS y tener el agente **y** el frontend
corriendo en local en menos de 20 minutos, sin experiencia previa en el proyecto.

### 0. Requisitos previos

- **Python 3.11** (no 3.10, no 3.12 — el proyecto se fija a 3.11 porque es lo que soportan las
  ruedas de `onnxruntime`/`rembg` que usamos).
- **Node.js 20+** y `npm` (para el frontend).
- **Git**.
- **Docker Desktop** (solo si vas a construir el contenedor — no hace falta para desarrollar ni
  correr los tests).
- Credenciales de **al menos uno** de los cuatro proveedores de modelo (Bedrock, Gemini,
  ChatGPT u Ollama local), **solo** si vas a usar el `VisionAgent`/`CatalogAgent` de verdad.
  Todo lo demás (recorte de imagen, API, tests) funciona sin ninguna credencial. Para empezar
  rápido sin cuenta de AWS, **Gemini es la opción más simple**: una API key gratuita en
  [aistudio.google.com](https://aistudio.google.com).

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
git clone https://github.com/GODE-Organization/snapflick.git
cd snapflick
```

### 2. Backend — entorno virtual e instalación

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
Si PowerShell bloquea el script de activación con un error de política de ejecución, corre una
vez (como el propio usuario, no como administrador):
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Windows (Git Bash):**
```bash
cd agent
py -3.11 -m venv .venv
source .venv/Scripts/activate
```

A partir de aquí verás `(.venv)` al inicio de la línea de comandos. Instala las dependencias
—desde la raíz del repo, con el `Makefile`:
```bash
make install
```
O manualmente si `make` no está disponible:
```bash
cd agent
pip install -e ".[dev]"
```
La primera instalación tarda un par de minutos porque `rembg` trae `scipy` y `scikit-image`.
Es normal.

**Si vas a usar Gemini, ChatGPT u Ollama** (no solo Bedrock), instala también el extra de ese
proveedor — son opcionales porque cada uno trae su propia librería pesada:
```bash
pip install -e ".[gemini]"    # Google Gemini
pip install -e ".[chatgpt]"   # OpenAI
pip install -e ".[ollama]"    # Ollama (cliente; el servidor corre aparte)
```

### 3. Backend — variables de entorno

```bash
cp agent/.env.example agent/.env
```
En Windows PowerShell, si `cp` no existe: `Copy-Item agent\.env.example agent\.env`.

Abre `agent/.env` y configura **al menos un proveedor de modelo**. El más rápido para empezar:
```bash
SNAPFLICK_MODEL_PROVIDER=gemini
SNAPFLICK_GEMINI_API_KEY=<tu-api-key-de-aistudio.google.com>
```
Si dejas `SNAPFLICK_MODEL_PROVIDER` vacío, el backend prueba los cuatro proveedores en orden
(Bedrock → Gemini → ChatGPT → Ollama) y usa el primero que responda — útil si tienes credenciales
para varios y no quieres elegir a mano.

Todo lo demás tiene default razonable para desarrollo local (`SNAPFLICK_S3_BUCKET` vacío = todo
en disco/SQLite local; `SNAPFLICK_CORS_ORIGINS=http://localhost:3000` ya apunta al frontend
local). Revisa `agent/.env.example` para la lista completa comentada.

### 4. Backend — correr los tests

```bash
make test
# o directamente:
cd agent && pytest -q
```
Estos tests **no** llaman a ningún proveedor de modelo ni descargan el modelo de `rembg` — usan
imágenes sintéticas generadas en memoria y un doble de prueba (mock) para los agentes. Deben
pasar en cualquier máquina, sin credenciales y sin conexión a internet.

### 5. Backend — levantar la API

```bash
make dev
```
Abre `http://localhost:8080/docs` para la API interactiva (Swagger UI), o prueba:
```bash
curl http://localhost:8080/ping
```

### 6. Frontend — instalar y correr

En otra terminal, con el backend ya corriendo en `:8080`:
```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```
Abre `http://localhost:3000`. `NEXT_PUBLIC_API_URL` en `.env.local` ya apunta a
`http://localhost:8080` por defecto — solo cámbialo si tu backend corre en otro puerto/host.

### 7. (Alternativa) Procesar un lote de prueba por CLI, sin frontend

Coloca unas fotos en `samples/input/` (y opcionalmente un fondo de marca en
`samples/backgrounds/`), luego:
```bash
make catalog
```
El resultado queda en `samples/output/catalogo.html` — ábrelo con doble clic en tu navegador,
las imágenes están incrustadas en el propio archivo. Este paso sí necesita credenciales válidas
del proveedor de modelo configurado, porque `VisionAgent`/`CatalogAgent` lo invocan de verdad.

### Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `pip install` falla instalando `onnxruntime`/`rembg` | Python distinto de 3.11, o CPU/OS sin rueda precompilada | Confirma `python --version` dentro del venv activado |
| `ModuleNotFoundError: snapflick` | El venv no está activado, o se instaló sin `-e` | Repite el paso 2 en orden |
| `/jobs` falla al extraer datos con `ValueError`/`NoCredentialsError` | Sin credenciales del proveedor de modelo, o proveedor equivocado en `SNAPFLICK_MODEL_PROVIDER` | Revisa `agent/.env`; con Gemini el error trae el nombre exacto de la variable que falta |
| `ImportError: cannot import name 'genai' from 'google'` | Fijaste `SNAPFLICK_MODEL_PROVIDER=gemini` (o chatgpt/ollama) pero no instalaste el extra de ese proveedor | `pip install -e ".[gemini]"` (o el que corresponda) |
| El frontend carga pero un job creado en una pestaña no aparece en otra / se pierde entre requests | La cookie de sesión (`sf_session`) es `Secure; SameSite=None` — depende de que el navegador trate `http://localhost` como origen confiable; si tu navegador no lo hace, usa Chrome/Edge en local o revisa que `SNAPFLICK_CORS_ORIGINS` incluya exactamente el origen del frontend | Confirma `agent/.env`: `SNAPFLICK_CORS_ORIGINS=http://localhost:3000` |
| Error de CORS en la consola del navegador | El origen del frontend no está en `SNAPFLICK_CORS_ORIGINS` (no acepta `*` junto con cookies) | Agrega el origen exacto (con protocolo y puerto) a esa variable, separado por coma si hay más de uno |
| `agent/.env` no se está leyendo | El proceso no se lanzó desde `agent/`, o el archivo no se llama exactamente `.env` | Confirma la ruta con `cat agent/.env` (o `Get-Content agent\.env` en PowerShell) |

---

## Uso

Con el backend y el frontend corriendo (o contra una URL ya desplegada), el flujo típico es:

1. **`/`** — dashboard con la lista de jobs (los tuyos, por sesión anónima).
2. **Subir fotos** — arrastra o selecciona las fotos del lote, elige un fondo de marca ya
   guardado o sube uno nuevo (o deja el fondo original de cada foto) → `POST /jobs`.
3. **Procesando** (`/jobs/[id]/processing`) — progreso en vivo por WebSocket (`/ws/jobs/{id}`),
   imagen por imagen.
4. **Revisión** (`/jobs/[id]/review`) — productos agrupados por categoría, comparación
   antes/después, edición de cualquier campo, agregar productos al lote, ocultar/eliminar
   alguno, o cambiarle el fondo a uno puntual.
5. **Catálogo final** (`/jobs/[id]/catalog`) — vista interna + el link público compartible
   (`/c/<job_id>`, el HTML autocontenido — abre sin backend, sin login, para clientes/socios).
6. **`/catalogs`** — histórico de catálogos ya generados.
7. **`/ajustes-ia`** — reglas en texto libre para instruir al `VisionAgent`/`CatalogAgent`
   (p. ej. "los precios siempre en COP", "agrupa snacks y golosinas juntos"), guardadas por
   sesión.

También hay una CLI (`make catalog` / `python -m snapflick.cli <carpeta>`) para generar un
catálogo sin pasar por el frontend, útil para pruebas rápidas o scripting.

### Referencia rápida de la API (`agent/`)

| Ruta | Qué hace |
|---|---|
| `GET /ping` | Health check — responde al instante, no carga nada |
| `POST /warmup` | Precarga `rembg` y resuelve el proveedor de IA (llamarlo antes de una demo) |
| `POST /jobs` | Crea un job — sube fotos (`multipart/form-data`) + fondo opcional |
| `GET /jobs` | Lista los jobs de la sesión actual |
| `GET /jobs/{id}` | Estado/detalle de un job (para polling si no usas el WebSocket) |
| `PATCH /jobs/{id}` | Edita metadata del job/catálogo |
| `DELETE /jobs/{id}` | Elimina un job |
| `POST /jobs/{id}/products` | Agrega un producto al lote ya procesado |
| `PATCH /jobs/{id}/products/{product_id}` | Edita un producto |
| `DELETE /jobs/{id}/products/{product_id}` | Elimina un producto del lote |
| `PATCH /jobs/{id}/products/{product_id}/background` | Cambia el fondo de un producto puntual |
| `GET /public/jobs/{id}` | Catálogo público (sin sesión) — lo que sirve `/c/{id}` en el frontend |
| `WS /ws/jobs`, `WS /ws/jobs/{id}` | Progreso en vivo |
| `POST /backgrounds`, `GET /backgrounds`, `DELETE /backgrounds/{key}` | Fondos de marca guardados |
| `GET /settings`, `PATCH /settings` | Reglas de agente en texto libre, por sesión |
| `POST /invocations` | Contrato de Bedrock AgentCore Runtime (no para el frontend — ver más abajo) |

Documentación interactiva completa en `http://localhost:8080/docs` con el backend corriendo.

---

## Cómo desplegarlo

Guía completa, paso a paso y verificada en vivo contra una cuenta real de AWS en
[`docs/02-guia-despliegue-aws.md`](docs/02-guia-despliegue-aws.md). Resumen:

- **Backend → Amazon ECS Express Mode** (recomendado; App Runner está cerrado a clientes
  nuevos desde 2026). Imagen Docker multi-arquitectura (`amd64`+`arm64` en un solo build,
  `infra/scripts/deploy.sh` o `make docker-build-push IMAGE_URI=...`) publicada en ECR.
- **Backend → Bedrock AgentCore Runtime** (opcional, además del anterior): el mismo contenedor
  ya implementa `POST /invocations`/`GET /ping` en :8080 y ya es multi-arch, así que registrarlo
  no cuesta nada extra — pero un AgentCore Runtime solo es alcanzable por
  `bedrock-agentcore:InvokeAgentRuntime` (IAM/SigV4), no por una URL pública, así que el
  frontend real no le habla directo a él.
- **Frontend → AWS Amplify Hosting**, con `web/` como raíz de la app (`web/amplify.yml` ya
  trae el build spec) — redespliega solo con cada `git push` a `main`.
- **Imágenes y catálogos → Amazon S3** (opcional; sin bucket, todo corre en disco local).

```bash
make docker-build          # imagen de un solo arch (host), para probar localmente
make docker-build-push IMAGE_URI=<cuenta>.dkr.ecr.<region>.amazonaws.com/snapflick:latest
```

Si construyes para una arquitectura distinta a la del host (p. ej. `arm64` desde un host
x86/amd64), ver `CLAUDE.md` ("Gotchas") sobre un problema conocido de `onnxruntime` bajo
emulación QEMU y cómo el `Dockerfile` ya lo evita.

---

## Estructura del repositorio

```
snapflick/
├── agent/                          servicio Python (Strands + FastAPI)
│   ├── src/snapflick/
│   │   ├── agents/                 VisionAgent, CatalogAgent
│   │   ├── tools/                  imagen, catálogo y storage (deterministas, sin modelo)
│   │   ├── models/schemas.py       contrato de datos compartido (Job, ProductSheet, ...)
│   │   ├── model_provider.py       Bedrock/Gemini/ChatGPT/Ollama, auto-detección
│   │   ├── job_store.py            estado de job: SQLite local / S3 en la nube
│   │   ├── pipeline.py             orquestación determinística del job
│   │   ├── main.py                 API FastAPI (/jobs, /ws, /invocations, /ping, ...)
│   │   └── cli.py                  procesar una carpeta desde consola
│   ├── tests/
│   └── Dockerfile                  multi-arch (amd64+arm64), modelo de rembg horneado
├── web/                             frontend Next.js (App Router, React 19, Tailwind 4)
│   └── src/
│       ├── app/                    páginas (dashboard, jobs, catálogo público, ajustes)
│       ├── components/             UI compartida (uploader, editor de producto, etc.)
│       └── lib/                    cliente de API y tipos compartidos con el backend
├── infra/                           CloudFormation (bucket S3) y scripts de despliegue/apagado
├── docs/                            arquitectura, alcance, guía de despliegue, revisión técnica
└── samples/                         fotos de ejemplo y fondos de marca para `make catalog`
```

## Documentación del proyecto

- [Arquitectura y decisiones de diseño](docs/00-arquitectura.md)
- [Alcance del producto](docs/01-alcance-del-producto.md)
- [Guía de despliegue en AWS](docs/02-guia-despliegue-aws.md)
- [Revisión técnica del scaffolding](docs/03-revision-tecnica.md)
- [`CLAUDE.md`](CLAUDE.md) — guía de arquitectura orientada a quien vaya a tocar el código

## Licencia

MIT — ver [LICENSE](LICENSE).
