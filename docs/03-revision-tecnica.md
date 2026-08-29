# Revisión técnica del scaffolding

Método: lectura completa del repo + instalación real de las dependencias en un venv
limpio (Python 3.11.9, `strands-agents 1.53.0`, `pydantic 2.13.4`,
`pydantic-settings 2.15.0`, `rembg 2.0.81`, `onnxruntime 1.29.0`, `pillow 12.3.0`,
`fastapi 0.141.1`) e inspección directa del código fuente instalado
(`inspect.signature`, `inspect.getsource`, lectura de `site-packages`). Todo lo marcado
"confirmado" se verificó así, no se infirió de memoria ni de documentación externa.

Todo lo que sigue, incluido `docker build`, se terminó verificando de forma real (ver
la sección "Verificación" al final).

---

## CRÍTICO — rompía el flujo central del producto

### 1. La barra de progreso nunca avanzaba — `agent/src/snapflick/main.py` y `agent/src/snapflick/pipeline.py`

```python
# main.py
def _process(job_id: str, paths: list[str], bg: str | None) -> None:
    try:
        JOBS[job_id] = run_job(paths, bg, job_id=job_id)   # <- reemplazo atómico al final
```
```python
# pipeline.py
def run_job(...) -> Job:
    job = Job(id=job_id or uuid.uuid4().hex[:12], ...)      # <- objeto NUEVO, local a la función
    ...
    for src in image_paths:
        ...
        job.processed_images += 1                            # <- muta la copia local, no la de JOBS
```

**Por qué se rompía:** `create_job` guarda un `Job` en `JOBS[job_id]` y lanza `_process`
como tarea de fondo. `_process` llamaba a `run_job`, que creaba **otro** objeto `Job`
completamente distinto y lo iba mutando en su propio scope. `JOBS[job_id]` seguía
apuntando al objeto original (con `processed_images=0`) durante todo el procesamiento, y
solo se reemplazaba de un tirón cuando `run_job` terminaba. Un cliente que hiciera
`GET /jobs/{id}` periódicamente vería `pending`/`processing` con `processed_images` fijo
en 0 y después, sin transición, `done` — la barra de progreso no existía en la práctica.

**Arreglo aplicado:** `run_job` ahora recibe y muta el `Job` que ya vive en `JOBS`, en
vez de crear uno nuevo:

```python
def run_job(job: Job, image_paths: list[str], background_path: str | None = None,
            workdir: Path | None = None) -> Job:
    job.status = JobStatus.PROCESSING
    ...
```

y en `main.py`:

```python
def _process(job_id: str, paths: list[str], bg: str | None) -> None:
    job = JOBS[job_id]
    try:
        run_job(job, paths, bg)          # muta el mismo objeto que ya está en JOBS
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.errors.append(str(exc))
```

Test de regresión: `tests/test_job_progress.py`.

---

### 2. El catálogo HTML no mostraba ninguna imagen al abrirlo — `agent/src/snapflick/templates/catalog.html.j2`

```html
<img src="{{ p.image.composed_path or p.image.source_path }}" alt="{{ p.sheet.name }}">
```

**Por qué se rompía:** `composed_path` es una ruta absoluta del sistema de archivos del
servidor. Un navegador no puede resolver rutas de archivo local ni rutas relativas al
*working directory* del proceso Python — solo entiende rutas relativas al HTML o URLs.
Abrir `catalogo.html` con doble clic (el caso de uso principal de este archivo) mostraba
tarjetas vacías con el icono de imagen rota.

**Arreglo aplicado:** las imágenes se incrustan como `data:` URI en base64 dentro del
propio HTML, no se sirven por ruta. Alternativas descartadas y por qué:
- *Rutas relativas al HTML*: funciona si el HTML vive en la misma carpeta que las
  imágenes y esa carpeta no se mueve, pero se rompe en cuanto alguien copia el `.html` a
  otro lado.
- *URLs servidas por la API* (`/files/...`): correcto para un catálogo "vivo" que
  consume un frontend, pero entonces el HTML solo sirve mientras la API esté corriendo —
  no es autocontenido.

`render_catalog_html` acepta un flag (`embed_images: bool = True`): por defecto incrusta
en base64; se puede desactivar si en algún momento se sirve el catálogo detrás de la
API en vez de como archivo independiente.

Test: `tests/test_catalog_tools.py` (decodifica el base64 con PIL y confirma dimensiones).

---

### 3. `web/` no tenía `package.json` — `web/README.md` y `Makefile`

**Por qué se rompía:** `make web` ejecuta `cd web && npm run dev`, que falla de
inmediato (`npm error code ENOENT... no package.json found`) porque `web/` solo tenía
un `README.md`. Más grave para el despliegue: la guía de AWS documenta desplegar con
**Amplify Hosting en modo monorepo, con `web` como raíz de la app**. Amplify detecta el
framework leyendo `package.json` en esa raíz; si no existe, la configuración de build
falla al conectar el repo.

**Arreglo aplicado:** se agregó un `package.json` mínimo válido (scripts `dev`/`build`/
`start` que fallan con un mensaje claro hasta que se inicialice el proyecto Next.js
real), para que Amplify pueda al menos parsear el monorepo sin fallar.

---

## ALTO

### 4. `Agent.structured_output()` está deprecado en la versión real del SDK — `agents/vision_agent.py` y `agents/catalog_agent.py`

**Confirmado leyendo el código fuente instalado** (`strands/agent/agent.py`,
`strands-agents==1.53.0`):

```python
def structured_output(self, output_model: type[T], prompt: AgentInput = None) -> T:
    ...
    warnings.warn(
        "Agent.structured_output method is deprecated."
        " You should pass in `structured_output_model` directly into the agent invocation."
        " see: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/",
        category=DeprecationWarning, stacklevel=2,
    )
    return run_async(lambda: self.structured_output_async(output_model, prompt))
```

No era un bug de disponibilidad — el método existe y funciona — pero emite un
`DeprecationWarning` en cada llamada, en cada test, en cada corrida del CLI, y el propio
SDK indica que se va a quitar.

**Arreglo aplicado**, confirmado contra la firma real de `Agent.__call__`:

```python
def extract_product_sheet(image_path: str, agent: Agent | None = None) -> ProductSheet:
    agent = agent or build_vision_agent()
    ...
    message = [
        {"text": "Extrae la ficha de este producto siguiendo tus reglas."},
        {"image": {"format": image_format, "source": {"bytes": path.read_bytes()}}},
    ]
    result = agent(message, structured_output_model=ProductSheet)
    return result.structured_output
```

`AgentResult.structured_output` es un campo real del dataclass
(`strands/agent/agent_result.py`), tipado como `BaseModel | None`. Mismo cambio en
`catalog_agent.plan_catalog`. Test: `tests/test_agents_mocked.py` (doble de prueba para
`Agent`, sin red).

### 5. El formato de bloque de imagen multimodal es correcto, con un límite real no cubierto

`{"image": {"format": "jpeg", "source": {"bytes": ...}}}` coincide exactamente con
`strands.types.media.ImageContent` (`TypedDict` con `format: ImageFormat` y
`source: ImageSource`), y `ImageFormat` es `Literal["png", "jpeg", "gif", "webp"]`
(confirmado con `typing.get_args`). `vision_agent.py` ya normaliza `jpg→jpeg`
correctamente.

**Punto real de riesgo no cubierto:** `ImageFormat` no incluye `heic`/`heif`. Las fotos
que salen directo de un iPhone con configuración de fábrica son **HEIC**, no JPEG. Ni
Pillow (sin el plugin `pillow-heif`, que no está en las dependencias) ni el `Literal` de
Strands aceptan ese formato — `remove_background` fallaría en `Image.open` con la
primera imagen HEIC que entre. No se soluciona en esta pasada porque agregar
`pillow-heif` implica una dependencia de sistema adicional (`libheif`) que puede
complicar el build ARM64. Documentado como límite conocido (ver "Ideas para después").

### 6. Dos entrypoints HTTP que competían por el mismo contrato — `agent_runtime.py` (eliminado) vs `main.py`

**Confirmado leyendo `bedrock_agentcore/runtime/app.py`:** `BedrockAgentCoreApp` **es**
una subclase de `Starlette` que ya registra sus propias rutas:

```python
Route("/invocations", self._handle_invocation, methods=["POST"]),
Route("/ping", self._handle_ping, methods=["GET"]),
```

y `app.run(port=8080)` levanta ese servidor directamente — es decir, era un servidor
HTTP completo y autosuficiente que cumplía el contrato de AgentCore por sí solo, sin
necesitar FastAPI ni uvicorn. Pero el `Dockerfile` arrancaba `uvicorn snapflick.main:app`
— la app **FastAPI**, que reimplementa `/ping` y `/invocations` a mano. Esto dejaba el
entrypoint de `BedrockAgentCoreApp` huérfano (nunca se ejecutaba en el contenedor real)
y mantenía dos implementaciones del mismo contrato — trabajo duplicado sin beneficio.

**Arreglo aplicado:** se eliminó el entrypoint basado en `BedrockAgentCoreApp`. FastAPI
(`main.py`) queda como único servidor, ya que el proyecto necesita rutas propias
(`/jobs`, `/jobs/{id}`, `/backgrounds`, servir `/files` estáticos) además del contrato
mínimo de AgentCore. El requisito de AgentCore no es "usar la clase
`BedrockAgentCoreApp`", es que el contenedor ARM64 exponga esas dos rutas en el puerto
8080 — cosa que `main.py` ya hace. El despliegue a AgentCore Runtime pasa a registrar
directamente el contenedor ya construido (`create-agent-runtime`) en vez de usar el CLI
`agentcore configure`/`launch` (que espera un entrypoint basado en `BedrockAgentCoreApp`
para generar su propio Dockerfile). Ver `02-guia-despliegue-aws.md`.

Si en el futuro se prefiere `BedrockAgentCoreApp` en vez de FastAPI, la alternativa es
recrear ese entrypoint y montar las rutas propias directamente sobre él con
`add_route`/`mount` de Starlette — más trabajo de reescritura, no se recomienda salvo
que haya una razón de peso para preferir la clase oficial del SDK sobre FastAPI.

### 7. `config.py` usaba `class Config` de Pydantic v1 con `pydantic-settings` v2 instalado

**Confirmado ejecutando el código real:** instanciar `Settings()` con `class Config`
anidada lanza `PydanticDeprecatedSince20` en cada import (se dispara en el primer
`import` de casi cualquier módulo del proyecto, incluyendo cada test). Seguía
funcionando —`env_prefix` sí se respetaba— pero es la forma incorrecta para v2.

**Arreglo aplicado**, confirmado que funciona igual sin warning:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SNAPFLICK_", extra="ignore")
    ...
```

### 8. `onnxruntime` (vía `rembg`) revienta el build de Docker bajo emulación QEMU en un host x86/amd64 — `agent/Dockerfile`

**Confirmado construyendo la imagen de verdad**, no solo leyendo el Dockerfile: el paso
que horneaba el modelo con `rembg.new_session(...)` fallaba con
`qemu: uncaught target signal 11 (Segmentation fault)` al construir con
`docker buildx build --platform linux/arm64` desde un host amd64. Se aisló la causa
paso a paso:
1. `new_session()` crea un `onnxruntime.InferenceSession` — se sospechó que ahí estaba
   el problema.
2. Se probó llamar solo a `download_models()` (que en teoría solo descarga el archivo
   `.onnx` vía `pooch`, sin tocar `onnxruntime`) — **también falló**, porque
   `rembg.sessions.dis_general_use` importa `.base`, que importa `onnxruntime` a nivel
   de módulo. Cualquier import de un `Session` de `rembg` arrastra `onnxruntime`.
3. Se probó un `import onnxruntime` completamente aislado, sin `rembg` de por medio —
   **también segfaultea**. Confirmado: el problema es `onnxruntime` corriendo bajo la
   emulación QEMU que usa `buildx` para construir `arm64` en un host `amd64`, no algo
   específico de `rembg` ni de este proyecto.

**Arreglo aplicado:** el paso de horneado descarga el archivo `.onnx` llamando
directamente a `pooch.retrieve()` con la misma URL y checksum que usa
`rembg`, sin importar `rembg` ni `onnxruntime` en absoluto durante el build. La primera
sesión de inferencia real se crea en runtime, ya nativamente en ARM64 (el entorno de
ejecución de AgentCore Runtime, no QEMU), momento en el que el archivo ya está
cacheado en `U2NET_HOME` — no hay descarga ni construcción de sesión en el primer
request.

**Verificado end-to-end:** `docker buildx build --platform linux/arm64 -t snapflick:local
./agent` termina en verde, y el contenedor resultante (`docker run -p 8081:8080
snapflick:local`, corriendo bajo emulación arm64) arranca y `GET /ping` responde
`{"status":"healthy"}`.

**Limitación conocida que queda documentada, no resuelta:** esto solo prueba que el
servidor arranca y que el archivo del modelo queda cacheado — no prueba que
`remove_background` funcione de verdad bajo QEMU, porque eso sí requiere crear un
`InferenceSession` real (el mismo problema del punto 1). Cualquier prueba end-to-end del
pipeline de imagen contra este contenedor tiene que correr en ARM64 nativo (Apple
Silicon, una instancia Graviton, o un runner ARM64 de CI), no en un host x86 vía
`buildx`+QEMU.

**Actualización — imagen ahora multi-arch (`linux/amd64` + `linux/arm64` en un solo
build+push):** este hallazgo sigue vigente sin cambios y es justamente lo que hace posible
el build multi-arch en un único comando. El paso de horneado (`pooch.retrieve`, sin
`rembg`/`onnxruntime`) no le importa bajo qué arquitectura corre, real o emulada —
es solo una descarga HTTP. Lo único que necesita arquitectura nativa (no emulación QEMU)
es crear un `InferenceSession` de verdad, y eso pasa exclusivamente en runtime, dentro del
contenedor ya construido para su arquitectura real (amd64 en ECS Express Mode/App Runner,
arm64 si además se registra en Bedrock AgentCore Runtime) — nunca durante el build ni bajo
emulación. Motivo por el que `agent/Dockerfile` ya no fija `--platform=linux/arm64`: el
`FROM python:3.11-slim-bookworm` publica manifiestos para ambas arquitecturas, y
`docker buildx build --platform linux/amd64,linux/arm64 --push` construye las dos sin
tocar `onnxruntime` en ningún momento del build.

---

## MEDIO

### 9. `datetime.utcnow()` deprecado — `models/schemas.py`
En Python 3.12 esto emite `DeprecationWarning`; en 3.11 (la versión del proyecto)
todavía no avisa, pero ya está marcado para remoción. Cambiado a
`datetime.now(UTC)` (y `JobStatus` a `enum.StrEnum`, sugerido por ruff con
`target-version = "py311"`).

### 10. `strands-agents-tools` era una dependencia declarada y nunca usada — `agent/pyproject.toml`
Confirmado con `grep -r "strands_tools" agent/` → cero resultados fuera del propio
`pyproject.toml`. Eliminada. Si en el futuro se quiere usar herramientas prearmadas de
Strands (ej. `http_request`, `file_read`), se vuelve a agregar en ese momento.

### 11. El decorador `@tool` en `image_tools.py` no estaba haciendo nada útil — `tools/image_tools.py`
**Confirmado, probando `DecoratedFunctionTool.__call__` directamente en el SDK real:**
delega al `_tool_func` original y devuelve el valor sin envolver nada
(`return self._tool_func(*args, **kwargs)`). O sea, llamar estas funciones "como
funciones normales" desde `pipeline.py` sí funcionaba correctamente con
`strands-agents==1.53.0` — no había un bug de tipo ahí.

Lo que sí era un problema de diseño: **ningún `Agent` del proyecto tenía estas
funciones en su lista de `tools=`** (confirmado con grep). El decorador `@tool`
comunica "el modelo puede decidir invocar esto", pero el modelo nunca las veía. Además,
son operaciones determinísticas (recortar, componer, miniaturizar) que no tiene sentido
delegarle a un LLM. **Arreglo aplicado:** se quitó el decorador `@tool` de las tres
funciones; quedan como funciones Python normales. Si en el futuro alguna quiere
exponerse a un agente, se envuelve en ese momento con una función delgada separada.

### 12. `storage_tools.py` es una abstracción sin usar — `tools/storage_tools.py`
Confirmado con grep: `Storage`, `LocalStorage`, `S3Storage`, `get_storage()` no se
importan en ningún otro archivo. `main.py` escribe archivos directo con
`shutil.copyfileobj`, sin pasar por esta interfaz. Es código muerto hoy, escrito
pensando en una futura migración a S3. **Decisión: sin tocar por ahora** — se adopta de
verdad cuando se migre el almacenamiento a S3 (ver "Ideas para después"), en vez de
usarla a medias ahora sin cambiar ningún comportamiento visible.

### 13. CI instalaba el stack pesado de `rembg` sin caché — `.github/workflows/ci.yml`
`pip install -e "./agent[dev]"` arrastra `scipy`, `scikit-image`, `onnxruntime`,
`pymatting` — instalar el equivalente tomó más de dos minutos incluso con buena
conexión. **Arreglo aplicado:** `cache: pip` en el step de `actions/setup-python`, y se
agregó el paso `ruff format --check` que faltaba.

### 14. Renombrado `snapcatalog` → `snapflick`
Aplicado en todo el árbol: paquete Python (`src/snapflick/`), prefijo de variables de
entorno (`SNAPFLICK_`), `Dockerfile`, `Makefile`, documentación, infraestructura y
licencia. Verificado con `grep -ri snapcatalog .` → cero resultados.

---

## BAJO

- **`agent/pyproject.toml`**: los rangos `>=X.0.0` son razonables y **todos los
  paquetes existen con esos nombres** (confirmado: `strands-agents`, `bedrock-agentcore`,
  `rembg[cpu]` son instalables tal cual). El extra `rembg[cpu]` es real (instala
  `onnxruntime` en vez de `onnxruntime-gpu`). No se encontró ninguna versión mínima
  imposible de satisfacer. Se dejan los rangos como están.
- **`bedrock_model_id` en `config.py`**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
  es un ID de *inference profile* de Bedrock (prefijo `us.`), formato correcto, pero no
  se pudo confirmar contra el servicio real que esté habilitado en `us-east-1` sin
  credenciales AWS. Verificar con `aws bedrock list-foundation-models` antes de
  desplegar (ver `02-guia-despliegue-aws.md`).
- **`onnxruntime` ARM64**: confirmado que existen wheels `manylinux_2_28_aarch64` para
  Python 3.11 tanto en la versión mínima fijada (1.19.0) como en la más reciente
  (1.29.0), y Debian bookworm (base del Dockerfile) trae glibc 2.36, compatible. El
  Dockerfile no tiene ningún problema de disponibilidad de wheel ahí — el problema real
  era el de emulación QEMU (ver hallazgo #8), no la disponibilidad del paquete.
- **`.env.example`** no incluía `SNAPFLICK_PRODUCT_MARGIN`, `SNAPFLICK_THUMBNAIL_SIZE`
  ni `SNAPFLICK_MAX_IMAGES_PER_JOB`, que sí existen en `Settings`. No rompía nada
  (tienen default), solo quedaba incompleto como documentación. Completado.
- **Dockerfile — `libgl1 libglib2.0-0`**: las dependencias reales de `rembg`
  (`scikit-image`, `scipy`, `pymatting`, `pooch`) no requieren OpenGL. Probablemente
  vinieron de un Dockerfile de ejemplo pensado para `opencv-python`, que este proyecto
  no usa. Se deja anotado como candidato a limpieza (el build ya funciona con ellas
  presentes, así que quitarlas es una optimización de tamaño de imagen, no una
  corrección).

---

## Ideas para después (fuera de alcance de esta revisión)

- Soporte HEIC/HEIF (fotos de iPhone) vía `pillow-heif`, si en el uso real con fotos de
  celular resulta ser un problema frecuente (ver hallazgo #5).
- Adoptar `storage_tools.py` de verdad cuando se migre el almacenamiento a S3, en vez de
  mantenerlo sin usar (ver hallazgo #12).
- Si más adelante se prefiere `BedrockAgentCoreApp` en vez de FastAPI (ver hallazgo #6),
  recrear un entrypoint con esa clase y mover `/jobs`, `/backgrounds` y el estático de
  `/files` a rutas de Starlette montadas ahí encima.
- Exportar a PDF / CSV Shopify — ver `01-alcance-del-producto.md`.
- Quitar `libgl1`/`libglib2.0-0` del Dockerfile si se confirma que ninguna dependencia
  transitiva de `scikit-image` los necesita en Debian (ver hallazgo BAJO).

---

## Hallazgo adicional de tooling (no listado originalmente)

`ruff check`/`ruff format` no pasaban contra el código tal como estaba. Dos causas
reales, no supuestas:
1. El código nunca se había corrido realmente contra `ruff format` — 14 de 20 archivos
   no cumplían el estilo por defecto de la versión instalada (`ruff 0.16.4`).
2. Sin `[tool.ruff.lint] select` explícito, `ruff check` usa en esta versión un
   conjunto de reglas más amplio que en versiones anteriores (incluye
   `flake8-bugbear`, `flake8-async`, etc.), y varias de esas reglas chocan con patrones
   normales de FastAPI (`File(...)` como default de argumento) o con decisiones de
   diseño deliberadas (el `except Exception` amplio en el pipeline, que existe
   justamente para que una imagen mala no tumbe el lote). Se fijó
   `select = ["E", "F", "I", "UP"]` en `pyproject.toml` para que el comportamiento de
   `ruff check` no dependa de qué versión de ruff se instale más adelante, y se aplicó
   `ruff format` una vez sobre todo el árbol.

---

## Verificación — qué se ejecutó realmente

- [x] `pip install -e "./agent[dev]"` — termina sin errores.
- [x] `pytest -q` — **14 tests pasan** (incluye `test_job_progress.py`,
      `test_agents_mocked.py`, `test_catalog_tools.py` y `test_pipeline_e2e.py`).
- [x] `ruff check src tests` — pasa limpio.
- [x] `ruff format --check src tests` — pasa limpio.
- [x] `uvicorn snapflick.main:app --port 8080` arranca; `GET /ping` responde
      `{"status":"healthy"}`.
- [x] `GET /openapi.json` se genera sin excepciones; se confirmaron las 5 rutas
      (`/ping`, `/invocations`, `/jobs`, `/jobs/{job_id}`, `/backgrounds`) y los 12
      schemas Pydantic, incluido `ProductSheet`.
- [x] Pipeline de imagen de punta a punta **sin Bedrock**, con `rembg` real (no
      mockeado): imagen sintética → `remove_background` → `compose_on_background` →
      `make_thumbnail`; se verificaron existencia y dimensiones exactas de cada archivo
      de salida (`tests/test_pipeline_e2e.py`, se salta automáticamente en CI porque
      descarga el modelo de rembg la primera vez).
- [x] Plantilla Jinja con datos falsos: se generó un catálogo real
      (3 productos, 2 categorías), se abrió con el navegador predeterminado del sistema
      y se confirmó por contenido que las 3 imágenes quedaron incrustadas en base64 y
      que ninguna ruta de filesystem se filtró al HTML.
- [x] `docker buildx build --platform linux/arm64 -t snapflick:local ./agent` — termina
      en verde (ver hallazgo #8 para el bug real que hubo que resolver primero).
- [x] `docker run -p 8081:8080 snapflick:local` arranca bajo emulación arm64 y
      `GET /ping` responde `{"status":"healthy"}`.
- [ ] Llamada real a Bedrock (`VisionAgent`/`CatalogAgent` contra el modelo de verdad) —
      sin credenciales de AWS en este entorno. Cubierto en cambio con dobles de prueba
      (`tests/test_agents_mocked.py`) que validan la lógica propia (formato del bloque
      de imagen, prompt del lote, desempaquetado de `structured_output`). Pendiente:
      correr `make catalog` con credenciales reales contra fotos de producto reales.
- [ ] `remove_background` (inferencia ONNX real) dentro del contenedor ARM64 — solo se
      verificó que el contenedor arranca y sirve `/ping`; la inferencia real de
      `onnxruntime` no se pudo probar en este host porque requiere ARM64 nativo, no la
      emulación QEMU de `buildx` (ver hallazgo #8). Pendiente: correr el pipeline
      completo contra el contenedor ya desplegado en AgentCore Runtime o en hardware
      ARM64 nativo.
