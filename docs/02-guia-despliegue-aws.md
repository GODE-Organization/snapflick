# Guía de despliegue en AWS

Guía técnica paso a paso para desplegar SnapFlick en una cuenta de AWS nueva. Asume cero
experiencia previa con AWS.

## 1. Cuenta y accesos base

### 1.1 Cuenta AWS
1. https://aws.amazon.com/ → "Crear una cuenta de AWS".
2. Elegir el plan **Basic (gratuito)**.

### 1.2 Alerta de presupuesto (hazlo antes que nada)
1. Consola AWS → **Billing and Cost Management** → **Budgets** → **Create budget**.
2. Tipo: *Cost budget* · define un monto mensual que tenga sentido para tu caso de uso.
3. Configura alertas al 50%, 80% y 100%.

### 1.3 Usuarios IAM (nunca uses la cuenta raíz para trabajar)
1. Consola → **IAM** → **Users** → **Create user**.
2. Marca acceso a la consola.
3. Para uso desde CLI/CI: pestaña **Security credentials** → **Create access key** →
   tipo *Command Line Interface*. Guarda `Access key ID` y `Secret access key` en un
   gestor de contraseñas. **Nunca en el repo.**
4. Los permisos mínimos que el proyecto necesita: `bedrock:InvokeModel`, acceso de
   lectura/escritura al bucket S3 que uses, y permisos de ECR/AgentCore si vas a
   desplegar el contenedor. Para desarrollo local, `AdministratorAccess` es más simple
   pero considera permisos acotados en cualquier entorno compartido o de producción.

### 1.4 Elegir región
Usa **`us-east-1` (Norte de Virginia)**. Es donde primero aparecen los modelos nuevos de
Bedrock. Cambiar de región a mitad de proyecto implica reconfigurar accesos y buckets.

### 1.5 Acceso a modelos de Bedrock
1. Consola → **Amazon Bedrock** → **Model access**.
2. **Manage model access** → habilita los modelos Claude de Anthropic con soporte de
   visión.
3. Envía la solicitud. Algunos modelos se aprueban al instante; otros pueden tardar horas.

### 1.6 AWS CLI
```bash
# Linux/macOS
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install

aws configure
# AWS Access Key ID: ...
# AWS Secret Access Key: ...
# Default region name: us-east-1
# Default output format: json

aws sts get-caller-identity   # debe imprimir tu cuenta → todo bien
```

### 1.7 Confirmar que Bedrock responde
```bash
aws bedrock list-foundation-models --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'claude')].modelId"
```
Si esto lista modelos, `agent/.env` ya puede apuntar a uno de ellos.

---

## 2. Almacenamiento y contenedor

### 2.1 Bucket S3 (cuando se migre del almacenamiento local a S3)
```bash
aws s3 mb s3://snapflick-<algo-unico> --region us-east-1
```
El nombre es global en todo AWS, así que agrega algo único.

Estructura de carpetas sugerida dentro del bucket:
```
uploads/<job_id>/original/     fotos crudas del usuario
uploads/<job_id>/processed/    PNG sin fondo y JPG compuesto
backgrounds/<user>/            fondos de marca guardados
catalogs/<job_id>/             HTML/JSON final
```

### 2.2 CORS del bucket (si el frontend sube directo a S3)
Consola → S3 → tu bucket → **Permissions** → **Cross-origin resource sharing (CORS)**:
```json
[{"AllowedHeaders":["*"],"AllowedMethods":["GET","PUT","POST"],"AllowedOrigins":["*"],"ExposeHeaders":["ETag"]}]
```
`*` en `AllowedOrigins` es cómodo para desarrollo; restringir el origen es una mejora de
seguridad recomendada antes de un uso más amplio.

### 2.3 Construir y publicar el contenedor en ECR
Bedrock AgentCore Runtime exige **ARM64**. Si tu máquina es Intel/AMD, usa
`docker buildx` (ver nota sobre `onnxruntime` bajo emulación QEMU en
`03-revision-tecnica.md`).

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws ecr create-repository --repository-name snapflick --region $REGION

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

docker buildx create --use
docker buildx build --platform linux/arm64 \
  -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/snapflick:latest \
  --push ./agent
```

### 2.4 Probar el contenedor en local antes de desplegar
```bash
docker run --rm -p 8080:8080 --env-file agent/.env snapflick:local
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"prompt":"ping"}'
```
Si esto no funciona en local, tampoco va a funcionar en la nube.

---

## 3. Despliegue

### Camino A (preferido) — Bedrock AgentCore Runtime

**Nota de arquitectura (ver `03-revision-tecnica.md`):** SnapFlick usa FastAPI como único
servidor (no la clase `BedrockAgentCoreApp`), así que el despliegue no pasa por el CLI
`agentcore configure`/`launch` (que espera un entrypoint basado en esa clase para generar
su propio Dockerfile) — en su lugar, se registra directamente el contenedor ya construido
y probado:

```bash
# 1) Construir y publicar la imagen (ver sección 2.3 arriba)
# 2) Registrar el runtime apuntando a la imagen en ECR
aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name snapflick \
  --agent-runtime-artifact '{"containerConfiguration":{"containerUri":"'"$ACCOUNT"'.dkr.ecr.'"$REGION"'.amazonaws.com/snapflick:latest"}}' \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --role-arn <ARN del rol IAM de ejecución> \
  --region $REGION
```

El rol de ejecución necesita permisos `bedrock:InvokeModel` y, si se usa S3, acceso al
bucket. Requisitos que el `Dockerfile` ya cumple: puerto 8080, `POST /invocations`,
`GET /ping`, ARM64.

### Camino B (plan de respaldo) — AWS App Runner

Mismo contenedor, despliegue en pocos minutos desde la consola.

1. Consola → **App Runner** → **Create service**.
2. Origen: **Container registry** → Amazon ECR → elegir `snapflick:latest`.
3. Puerto: `8080`. Health check: `/ping`.
4. Variables de entorno: las de `.env.example`.
5. Rol de instancia con permisos `bedrock:InvokeModel` y acceso al bucket S3.
6. Create & deploy → entrega una URL `https://xxxx.awsapprunner.com`.

App Runner cobra por hora de contenedor activo — pausa el servicio cuando no lo uses.

### Frontend en Amplify Hosting
1. Consola → **AWS Amplify** → **Deploy an app** → GitHub → autorizar → elegir el repo.
2. **Monorepo:** marca la casilla y pon `web` como raíz de la app.
3. Variable de entorno `NEXT_PUBLIC_API_URL` = la URL de la API desplegada.
4. Save and deploy. Cada push a `main` redespliega automáticamente.

---

## 4. Antes de exponer la URL públicamente

- [ ] La URL responde desde una red distinta a la de desarrollo (p. ej. datos móviles).
- [ ] Ninguna clave de acceso quedó en el historial de git (`git log -p | grep -i "aws_secret"`).
- [ ] La alerta de presupuesto no se ha disparado.
- [ ] CORS, límites de tamaño de archivo y timeouts están configurados razonablemente.

## Costos estimados

| Servicio | Estimado |
|---|---|
| Bedrock (modelo con visión, ~500 imágenes de prueba) | USD 3–8 |
| S3 (unos pocos GB) | < USD 1 |
| ECR (una imagen) | < USD 1 |
| App Runner o AgentCore (encendido a ratos) | USD 5–15 |
| Amplify Hosting | Gratis en capa gratuita |
| **Total** | **USD 10–25** |
