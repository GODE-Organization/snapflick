# Alcance del producto

## Qué es SnapFlick

Un agente que convierte fotos caseras de productos en un catálogo publicable:

1. Recorta el producto y elimina el fondo (`rembg`, local, sin costo por imagen).
2. Compone el producto sobre un fondo de marca que el usuario guardó previamente.
3. Lee el empaque con un modelo multimodal de Amazon Bedrock y extrae nombre, marca,
   presentación, descripción, ingredientes y código de barras.
4. Normaliza y **categoriza** el lote completo para que quede agrupado de forma coherente.
5. Genera la ficha de producto (JSON) y arma el catálogo HTML por categoría.

## MVP (mínimo indispensable)

- Cargar N fotos desde el frontend o una carpeta.
- Quitar el fondo y componer sobre un fondo de marca guardado.
- Extraer nombre, marca, presentación/peso y descripción del empaque.
- Asignar categoría automáticamente.
- Generar catálogo HTML navegable + JSON exportable.
- Desplegado y accesible por URL pública.

## Deseable (si sobra tiempo)

- Exportar catálogo a PDF.
- Exportar CSV compatible con Shopify / catálogo de WhatsApp Business.
- Sugerencia de precio o texto de marketing.
- Corrección manual de la ficha desde el frontend.

## Fuera de alcance (deliberadamente)

- Autenticación de usuarios / multi-tenant.
- App móvil nativa.
- Reconocimiento de código de barras contra una base de datos externa.
- Entrenar cualquier modelo propio.

Ver `03-revision-tecnica.md` para las decisiones de arquitectura que se ajustaron desde
el diseño original y por qué.
