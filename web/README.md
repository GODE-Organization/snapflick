# Frontend (Next.js)

Para inicializar el proyecto:

```bash
npx create-next-app@latest . --typescript --tailwind --app --eslint --src-dir --no-import-alias
npm i swr
```

## Variables de entorno
```
NEXT_PUBLIC_API_URL=http://localhost:8080
```

## Pantallas mínimas para el MVP

1. **Subir** — arrastrar fotos + seleccionar/subir fondo de marca → `POST /jobs`
2. **Progreso** — sondear `GET /jobs/{id}` cada 2 s y mostrar barra + contador
3. **Catálogo** — productos agrupados por categoría, tarjeta con imagen compuesta y ficha
4. **Comparación antes/después** — deslizador sobre una foto original vs. procesada.

## Despliegue
AWS Amplify Hosting, con `web` como raíz de la app en la configuración de monorepo.
