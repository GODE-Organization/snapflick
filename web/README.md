# Frontend (Next.js)

```bash
cd web
npm install
cp .env.example .env.local   # ajustar NEXT_PUBLIC_API_URL si el backend no corre en :8080
npm run dev
```

Requiere el backend corriendo (`make dev` desde la raíz del repo, agent/ en :8080).

## Variables de entorno

Ver `.env.example`. `NEXT_PUBLIC_API_URL` apunta al FastAPI de `agent/`.

## Pantallas

1. **Dashboard** (`/`) — lista de jobs.
2. **Configuración** (`/new`) — subir fotos + elegir/subir fondo de marca → `POST /jobs`.
3. **Procesando** (`/jobs/[id]/processing`) — sondea `GET /jobs/{id}` cada 2s.
4. **Revisión de Lote** (`/jobs/[id]/review`) — productos agrupados por categoría, detalle
   con comparación antes/después.
5. **Catálogo Final** (`/jobs/[id]/catalog`) — vista interna + enlace al catálogo público
   (el HTML autocontenido que genera `tools/catalog_tools.render_catalog_html` en el backend).

Diseño portado desde la propuesta generada con el MCP de Stitch (proyecto "SnapFlick AI
Catalog Generator", tema Lumina AI) — tokens en `src/app/globals.css` (`@theme`).

## Despliegue

AWS Amplify Hosting, con `web` como raíz de la app en la configuración de monorepo (`amplify.yml`
en esta carpeta ya trae el build spec). Setear `NEXT_PUBLIC_API_URL` en las variables de
entorno de la consola de Amplify, apuntando a la API desplegada.
