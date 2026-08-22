# Arquitectura

## Diagrama

Ver [`architecture.mermaid`](architecture.mermaid).

## Estructura del repositorio

Monorepo con `agent/` (Python) y `web/` (Next.js) como carpetas hermanas, cada una con
su propio build. Razones para un solo repositorio en vez de dos:

- El frontend y el backend comparten el contrato de datos de la ficha de producto
  (`ProductSheet`). En un monorepo esa definición vive en un solo archivo
  (`agent/src/snapflick/models/schemas.py`) y el frontend consume el JSON Schema que
  expone FastAPI en `/openapi.json`, sin duplicarlo a mano.
- El despliegue no obliga a separar repos: se despliegan artefactos distintos desde el
  mismo árbol de código (el backend va a un contenedor, el frontend a Amplify o
  S3+CloudFront).

Si en algún momento hace falta separarlos, `git subtree split` lo hace en un comando.

## Los dos agentes

1. **VisionAgent** — recibe la imagen recortada, la analiza con un modelo multimodal de
   Bedrock y devuelve una `ProductSheet` estructurada (salida tipada con Pydantic, que
   Strands soporta nativamente).
2. **CatalogAgent** — recibe N fichas, las normaliza, decide categorías coherentes entre
   todas, detecta duplicados y sugiere el orden del catálogo.

El orquestador (`pipeline.py`) coordina el flujo y aísla los fallos por imagen — es
código de control determinístico, no un tercer agente: no hay ninguna decisión ahí que
valga la pena delegarle a un modelo. Ver `03-revision-tecnica.md` para el razonamiento
completo detrás de por qué el diseño no incluye un tercer agente "orquestador".

## Flujo de un job

1. `POST /jobs` con N imágenes → se guardan (local en desarrollo, S3 en producción) →
   `job.status = pending`.
2. El pipeline toma el job y por cada imagen:
   a. `remove_background` (rembg, CPU, local al contenedor) → PNG con alfa.
   b. `_autocrop_alpha` → recorte al bounding box del producto.
   c. `compose_on_background` → JPG final sobre el fondo de marca.
   d. `VisionAgent(imagen original)` → `ProductSheet` con salida estructurada.
   e. Si falla → se marca esa imagen como `failed` y el job continúa con las demás.
3. `CatalogAgent(todas las fichas)` → categorías coherentes + orden.
4. `render_catalog_html` → HTML autocontenido (imágenes incrustadas en base64) + JSON.
5. `job.status = done`, el cliente que hace polling de `GET /jobs/{id}` ve el resultado.

## Decisiones de diseño y su justificación

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| rembg local | API de terceros / modelo de Bedrock para recorte | Gratis, offline, sin cuotas ni latencia de red; el modelo se hornea en la imagen Docker |
| Salida estructurada de Strands | Parsear JSON de texto libre | Elimina la clase de bug más frecuente; Pydantic valida en el borde |
| Categorizar el lote completo | Categorizar producto por producto | Evita categorías duplicadas semánticamente ("Bebida" vs "Bebidas") |
| Dos agentes, no tres | Un "Orchestrator" como tercer agente | El flujo de control es determinístico; nada ahí justifica delegarle una decisión a un modelo |
| Un solo servidor FastAPI | `BedrockAgentCoreApp` + FastAPI en paralelo | El proyecto necesita rutas propias (`/jobs`, `/backgrounds`, `/files`) además del contrato de AgentCore; mantener dos servidores duplicaba trabajo |
| Job asíncrono | Petición HTTP síncrona | Un lote de fotos × modelo multimodal supera cualquier timeout razonable de request/response |
| Confianza explícita por campo | Rellenar campos con lo que sea | El agente admite lo que no sabe (`confidence: "low"`, `null` en vez de inventar) |
| Catálogo HTML con imágenes incrustadas (base64) | Rutas de archivo o URLs servidas por la API | El HTML tiene que poder abrirse con doble clic y verse completo sin depender de que la API siga corriendo |

## Contrato de datos

`ProductSheet` es el corazón del sistema y lo comparten agente, API y frontend. Está
definido una sola vez en `agent/src/snapflick/models/schemas.py` y el frontend consume
el JSON Schema que expone FastAPI en `/openapi.json`.
