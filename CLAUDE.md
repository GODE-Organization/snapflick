# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SnapFlick converts homemade product photos into a publishable catalog: it removes the
background, composes the product onto a saved brand background, reads the packaging with
a multimodal model to extract structured product data, categorizes the whole batch
coherently, and renders an HTML/JSON catalog.

Monorepo: `agent/` (Python — Strands Agents SDK + FastAPI) and `web/` (Next.js). `web/amplify.yml`
has the Amplify Hosting build spec (`appRoot: web`); `NEXT_PUBLIC_API_URL` (documented in
`web/.env.example`) is what `web/src/lib/api.ts` reads to reach the agent API.

## Commands

All Python commands assume a venv at `agent/.venv` (Python 3.11 — not 3.10, not 3.12: see
"Gotchas" below) created and activated from inside `agent/`:

```bash
cd agent
python3.11 -m venv .venv          # macOS/Linux
py -3.11 -m venv .venv            # Windows
source .venv/bin/activate         # macOS/Linux
.venv\Scripts\Activate.ps1        # Windows PowerShell
```

From the repo root (`Makefile` wraps all of these):

```bash
make install        # cd agent && pip install -e ".[dev]"
make test            # cd agent && pytest -q
make lint             # cd agent && ruff check --fix src tests && ruff format src tests
make dev              # cd agent && uvicorn snapflick.main:app --reload --host 0.0.0.0 --port 8080
make catalog          # CLI: processes samples/input/ into samples/output/catalogs/<job_id>/catalogo.html
make docker-build     # builds a single-arch image (host arch) for local dev/test
make docker-build-push IMAGE_URI=...  # multi-arch (amd64+arm64) build+push in one command
make docker-run       # runs the built container locally on :8080
make warmup           # POST /warmup — pre-warms rembg + the model provider before a demo
```

Run a single test: `cd agent && pytest tests/test_pipeline_e2e.py::test_pipeline_de_imagen_corre_de_punta_a_punta -q`

`ruff check` uses an explicit `select = ["E", "F", "I", "UP"]` in `agent/pyproject.toml` —
don't rely on ruff's default rule set, it has grown across versions and pulls in
`flake8-bugbear`/`flake8-async` rules that conflict with deliberate patterns in this
codebase (FastAPI's `File(...)` argument defaults, the broad `except Exception` in the
pipeline).

`tests/test_pipeline_e2e.py` runs the real image pipeline (rembg + Pillow, no mocking) and
is skipped automatically when `CI=true` is set, because the first run downloads rembg's
ONNX model (~176 MB). It runs normally in local dev once that model is cached.

## Architecture

### Two agents, not three

`VisionAgent` (`agents/vision_agent.py`) reads one product photo and returns a validated
`ProductSheet` via Strands structured output. `CatalogAgent` (`agents/catalog_agent.py`)
receives the *entire batch* of extracted sheets at once and decides coherent categories —
categorizing product-by-product instead would produce near-duplicate categories ("Bebida"
vs "Bebidas"). `pipeline.py` (`run_job`) is deterministic control flow, not a third agent:
there's no decision there worth delegating to a model.

Both agents call `agent(prompt_or_message, structured_output_model=SomeModel)` and read
`.structured_output` off the result — **not** the deprecated `Agent.structured_output()`
method (it still works but emits `DeprecationWarning` on every call).

### Job mutation, not replacement

`pipeline.run_job(job: Job, image_paths, ...)` takes an existing `Job` object and mutates
it in place (status, `processed_images`, `products`) rather than constructing and returning
a new one. `main.py`'s `_process()` and `/invocations`, and `cli.py`, all create the `Job`
first, register it (in `main.py`, into the in-memory `JOBS` dict), and then call
`run_job(job, ...)`. This matters because `JOBS` in `main.py` is a plain dict keyed by job
id — if `run_job` ever went back to creating its own `Job` and returning it, progress
polling via `GET /jobs/{id}` would break silently (see `docs/03-revision-tecnica.md`,
finding #1, for the exact failure mode this replaced).

### Single HTTP server

`main.py` (FastAPI) is the *only* server. It implements the Bedrock AgentCore Runtime
contract by hand (`POST /invocations`, `GET /ping` on :8080) alongside the product's own
routes (`/jobs`, `/backgrounds`, `/files`). There is no `BedrockAgentCoreApp` entrypoint in
this repo — that class is itself a self-sufficient Starlette server, and running it
alongside FastAPI would mean maintaining the same contract twice. Deployment to AgentCore
Runtime registers the built container directly rather than going through the
`agentcore configure`/`launch` CLI (which expects a `BedrockAgentCoreApp` entrypoint to
generate its own Dockerfile).

**This dual-serving only works over plain HTTP** (ECS Express Mode, App Runner, local dev) —
it does *not* mean the product's own routes become reachable once the container is actually
registered *as* an AgentCore Runtime resource. External access to an AgentCore Runtime goes
exclusively through the AWS SDK/CLI action `bedrock-agentcore:InvokeAgentRuntime` (IAM/SigV4,
JSON-only, session-based) — `/invocations` and `/ping` are the only routes ever reached from
outside, no matter how many others the container serves. So `POST /jobs` (multipart upload),
`GET /jobs/{id}` polling, and `/ws/jobs*` are unreachable once deployed that way. AgentCore
Runtime registration is worth doing (see `docs/02-guia-despliegue-aws.md`) as a demonstration
of real Bedrock AgentCore integration, but ECS Express Mode/App Runner — which expose the
whole app over plain HTTP — are what the frontend actually talks to.

### Image tools are plain functions, not Strands `@tool`s

`tools/image_tools.py` (`remove_background`, `compose_on_background`, `make_thumbnail`) are
deterministic and called directly from `pipeline.py`. They are intentionally *not*
decorated with Strands' `@tool` — no agent in this project decides when to crop or resize
an image; that always happens, in the same order, every time. Don't add `@tool` back
without an actual agent that needs to choose whether to call them.

### Catalog HTML is self-contained

`tools/catalog_tools.render_catalog_html(job, output_path, embed_images=True)` embeds every
product image as a base64 `data:` URI directly in the HTML (see
`templates/catalog.html.j2`, `image_srcs[p.id]`). This is deliberate: the catalog is meant
to be opened by double-clicking the file, so it can't depend on relative paths or a running
API server. Pass `embed_images=False` only if the HTML will be served behind a URL that can
resolve the image paths itself.

### Config

`config.py`'s `Settings` (pydantic-settings `BaseSettings`) reads `SNAPFLICK_*` env vars
from `agent/.env` (see `agent/.env.example` for the full list, including
`SNAPFLICK_BEDROCK_MODEL_ID`, `SNAPFLICK_AWS_REGION`, `SNAPFLICK_DATA_DIR`,
`SNAPFLICK_CANVAS_SIZE`, `SNAPFLICK_PRODUCT_MARGIN`, `SNAPFLICK_THUMBNAIL_SIZE`,
`SNAPFLICK_MAX_IMAGES_PER_JOB`). `settings` is a module-level singleton imported by name
across the codebase — patch attributes on it in tests (`monkeypatch.setattr(settings, ...)`
via whichever module imported it) rather than reassigning the name.

### Four interchangeable model providers, with auto-fallback

`model_provider.py`'s `build_model()` supports `bedrock`, `gemini`, `chatgpt` (OpenAI), and
`ollama` — switching is `SNAPFLICK_MODEL_PROVIDER=<name>` plus that provider's key/host, no
agent code changes. When `SNAPFLICK_MODEL_PROVIDER` is unset, `build_model()` runs in
auto-detect mode: it tries each provider in `FALLBACK_ORDER` (bedrock → gemini → chatgpt →
ollama), building the model and firing one real minimal call (`_probe`) to confirm it
actually responds; the first one that doesn't raise wins and is cached at module level
(`_resolved_model`) for the rest of the process. When `SNAPFLICK_MODEL_PROVIDER` *is* set,
only that provider is tried — no fallback, the error propagates as-is. Optional deps
(`google-genai`, `openai`, `ollama`) are imported lazily inside each `_build_*()` so a
missing package just makes that candidate fail over to the next one in auto mode, rather
than crashing at import time.

`pipeline.py`'s `_friendly_error_message()` translates raw provider exceptions (Gemini's
`APIError`, or anything exposing an HTTP-like `.status_code`) into short Spanish messages
for the frontend instead of dumping the raw exception `str()` (which for Gemini includes
the full JSON error body) — extend `_GEMINI_STATUS_MESSAGES` / `_HTTP_CODE_MESSAGES` there
when a new provider's error shape needs a friendlier mapping.

### Gemini rate limits and extraction caching

`retry.py`'s `with_retry()` wraps the `VisionAgent`/`CatalogAgent` calls in `pipeline.py`
(`extract_product_sheet`, `plan_catalog`) with exponential backoff, but only for errors it
recognizes as rate-limiting (`status_code == 429`, or Gemini's `RESOURCE_EXHAUSTED`) — any
other exception propagates immediately into `run_job`'s existing per-image `except`, so a
genuinely bad image still fails fast instead of burning through retries on something that was
never going to succeed. This matters most against Gemini's free tier (per-minute/per-day
limits) during repeated demo runs or dev iteration.

`pipeline._cached_extract_product_sheet` additionally caches extraction results through
`Storage` at `cache/<hash>.json`, where the hash covers *(resolved provider, resolved model
id, `VisionAgent.PROMPT_VERSION`, image bytes)* — not just the image. Hashing in the
provider/model/prompt version is deliberate: without it, editing `SYSTEM_PROMPT` would keep
silently serving old cached extractions, which reads as a mysterious "my prompt change did
nothing" bug rather than what it actually is (a stale cache hit). Bump `PROMPT_VERSION` in
`agents/vision_agent.py` by hand whenever the prompt changes in a way that should affect
extraction. `model_provider.resolved_provider()`/`resolved_model_id()` exist specifically to
name the provider/model actually in play (important in auto-detect mode, where it may not be
the first candidate in `FALLBACK_ORDER`).

### Storage

`tools/storage_tools.py` defines a `Storage` interface (`LocalStorage`/`S3Storage`) picked
by `get_storage()` based on `SNAPFLICK_S3_BUCKET`. Image processing (rembg, Pillow) always
writes to local disk under `SNAPFLICK_DATA_DIR` first — those libraries need real
filesystem paths — but `main.py`'s `_sync_job_to_storage()` then replicates every finished
job artifact (originals, cutouts, composed images, thumbnails, catalog html/json,
backgrounds) to S3 when `SNAPFLICK_S3_BUCKET` is set, and `_to_url()` serves presigned S3
URLs instead of local `/files/...` paths in that case. `list_backgrounds()` goes through
`Storage.list_keys()` (implemented for both `LocalStorage` and `S3Storage`), so it works
correctly behind a multi-instance deployment too — no local-disk-only limitation anymore.

`paths.py` centralizes the key convention used by both local disk and S3 (`uploads/<id>/original/`,
`uploads/<id>/processed/`, `backgrounds/<key>`, `catalogs/<id>/`, `jobs/<id>.json`,
`cache/<hash>.json`) — `main.py` and `pipeline.py` build every local path through these
functions specifically so that `_sync_job_to_storage`'s local-path-relative-to-`DATA`-as-S3-key
logic produces the right key automatically, without a second hardcoded convention to keep in
sync.

`Storage` also exposes `exists(key)` (used by the extraction cache, see "Gemini rate limits
and caching" below) and `list_keys(prefix)`.

### Job persistence: SQLite locally, S3 in the cloud, behind the same interface pattern

`job_store.py` mirrors the `Storage`/`get_storage()` pattern for job **state** (as opposed to
job artifacts, covered above): `JobStateStore` (`save`/`get`/`all`), with `SqliteJobStore`
(wraps the existing `db.JobStore`) and `S3JobStore` (one JSON blob per job at
`jobs/<job_id>.json`), picked by `get_job_store()` based on `SNAPFLICK_S3_BUCKET` — same
switch as `get_storage()`. `main.py`'s `STORE` is now `get_job_store()` instead of a hardcoded
`db.JobStore`; every other call site (`STORE.save`, `STORE.all`) is unchanged. This matters
because SQLite is a local file — on ECS Express Mode/App Runner the container's disk is
ephemeral and there can be multiple instances behind the same service, so with
`SNAPFLICK_S3_BUCKET` unset (local dev), state stays in SQLite exactly as before; with it set,
state moves to S3 and survives redeploys/scaling. `S3JobStore.all()` lists everything under
`jobs/` and downloads each object to sort by `created_at` — O(n) reads, fine at
demo/hackathon scale, a real limitation at large job-list scale (would want a separate index,
e.g. DynamoDB, at that point).

`main.py`'s `JOBS` dict is still a read-through in-memory cache seeded from `STORE.all()` at
import time, not the source of truth. Every mutation point (`create_job`, `_process`,
`update_product`) calls `STORE.save(job)` right after mutating the in-memory object, and
`pipeline.run_job` accepts an optional `on_update` callback (wired to `STORE.save` in
`_process`) so progress is persisted incrementally per image, not only at request boundaries
— a crash mid-batch loses at most one image's worth of state, not the whole job.

`Job` is stored as a single JSON blob (`model_dump_json()`/`model_validate_json()`) in both
backends rather than modeled as relational tables/columns for products/plan — this mirrors
"Job mutation, not replacement" above: `Job` is already treated everywhere as one
self-contained tree, so the persistence layer matches that shape instead of fighting it. In
`SqliteJobStore`, `status`/`created_at` are additionally duplicated into their own SQLite
columns only so `JobStore.all()` can order rows without deserializing every one — `db.py`'s
`JobStore` opens its own `sqlite3` connection per method call, since it's called from both the
request thread and the `BackgroundTasks` thread that runs `_process`, and `sqlite3`
connections aren't safe to share across threads. The db file lives at
`{SNAPFLICK_DATA_DIR}/snapflick.db` (gitignored, alongside the rest of `data/`).

## Gotchas

- **Python must be 3.11.** The `onnxruntime`/`rembg` wheels this project depends on target
  3.11; running with 3.10 or 3.12 from the wrong interpreter is the most common source of
  "works on my machine" issues (usually shows up as `ModuleNotFoundError: snapflick` when
  the venv isn't the one active, or a wheel build failure otherwise).
- **Building the Docker image for a non-host architecture via `docker buildx` (e.g. `arm64`
  from an x86/amd64 host, needed for Bedrock AgentCore Runtime) crashes if anything imports
  `onnxruntime` during the build** (confirmed: even a bare `import onnxruntime` segfaults
  under QEMU user-mode emulation). The `Dockerfile` works around this by downloading rembg's
  `.onnx` model file with `pooch` directly, without importing `rembg` or `onnxruntime` at
  build time — the real inference session gets created at runtime, natively, inside the
  already-built container for its real architecture, never under emulation. This is also what
  makes the multi-arch build (`linux/amd64,linux/arm64` in one `buildx` invocation, see
  `make docker-build-push` / `infra/scripts/deploy.sh`) safe. See `docs/03-revision-tecnica.md`,
  finding #8, before touching that `RUN` step.
- **AWS App Runner is closed to new customers** (existing customers keep working normally;
  AWS isn't adding features). The primary deploy path is now Amazon ECS Express Mode — see
  `docs/02-guia-despliegue-aws.md` for the sourced note, the CLI commands, and — important —
  the cost difference: ECS Express Mode's auto-created ALB bills hourly regardless of traffic,
  unlike App Runner which can be paused. Delete the service between demo sessions with
  `infra/scripts/teardown.sh`, don't just scale it to zero.
- **HEIC/HEIF photos aren't supported.** `strands.types.media.ImageFormat` and Pillow (no
  `pillow-heif`) don't accept HEIC, which is what iPhones export by default. Not fixed —
  documented as a known limitation.
- Running the full `/jobs` flow (or `make catalog`) requires at least one working model
  provider — the image pipeline (crop/compose) runs fully local, but `VisionAgent`/
  `CatalogAgent` will fail per-image without one (`NoCredentialsError` for Bedrock, a clear
  "Falta SNAPFLICK_GEMINI_API_KEY"-style `ValueError` for gemini/chatgpt, connection refused
  for ollama). The test suite covers the agent logic with a fake `Agent` double instead (see
  `tests/test_agents_mocked.py`) so this isn't required to develop or run tests.
- `google-genai`, `openai`, and `ollama` are optional extras (`pip install -e ".[gemini]"`,
  `".[chatgpt]"`, `".[ollama]"`) — only `pip install -e ".[dev]"` (which doesn't pull them
  in) is required by `make install`. In auto-detect mode (`SNAPFLICK_MODEL_PROVIDER` unset)
  a provider whose package isn't installed just fails over to the next one; install the
  extras for whichever providers you actually want auto-detect to be able to pick.

See `docs/00-arquitectura.md`, `docs/01-alcance-del-producto.md`,
`docs/02-guia-despliegue-aws.md`, and `docs/03-revision-tecnica.md` for more detail on any
of the above.
