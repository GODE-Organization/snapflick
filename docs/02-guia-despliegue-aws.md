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

### 2.1 Bucket S3
```bash
aws s3 mb s3://snapflick-<algo-unico> --region us-east-1
```
El nombre es global en todo AWS, así que agrega algo único. Con `SNAPFLICK_S3_BUCKET`
seteado, tanto los artefactos de cada job como el estado del job mismo van a S3 — sin ese
valor, todo sigue en disco local (ver CLAUDE.md, secciones "Storage" y "Job persistence").

Estructura real de claves dentro del bucket (`agent/src/snapflick/paths.py`):
```
uploads/<job_id>/original/<archivo>      fotos crudas del usuario
uploads/<job_id>/processed/<archivo>     PNG sin fondo y JPG compuesto sobre el fondo
backgrounds/<clave>                      fondos de marca guardados
catalogs/<job_id>/catalogo.html|json     catálogo final
jobs/<job_id>.json                       estado del job (ver job_store.py)
cache/<hash>.json                        caché de extracción (proveedor+modelo+prompt+imagen)
```

### 2.2 CORS del bucket (si el frontend sube directo a S3)
Consola → S3 → tu bucket → **Permissions** → **Cross-origin resource sharing (CORS)**:
```json
[{"AllowedHeaders":["*"],"AllowedMethods":["GET","PUT","POST"],"AllowedOrigins":["*"],"ExposeHeaders":["ETag"]}]
```
`*` en `AllowedOrigins` es cómodo para desarrollo; restringir el origen es una mejora de
seguridad recomendada antes de un uso más amplio.

### 2.3 Construir y publicar el contenedor en ECR

La imagen es **multi-arquitectura** (`linux/amd64` + `linux/arm64`) en un único build+push —
`infra/scripts/deploy.sh` hace esto automáticamente. amd64 es lo que corre en ECS Express
Mode/App Runner; arm64 es lo que exige Bedrock AgentCore Runtime, si además se registra ahí
(ver sección 3). Un único manifiesto multi-arch sirve para ambos, así que no hay que elegir
de antemano ni mantener dos builds.

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws ecr create-repository --repository-name snapflick --region $REGION

aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$REGION.amazonaws.com

docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/snapflick:latest \
  --push ./agent
```

O simplemente `infra/scripts/deploy.sh`, que hace exactamente esto. Para probar solo en tu
máquina (arquitectura del host, sin publicar), usa `make docker-build`.

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

> **AWS App Runner está cerrado a clientes nuevos** desde la fecha de este cambio — cuentas
> existentes con App Runner siguen funcionando normal, pero AWS "no planea introducir
> nuevas funcionalidades" y recomienda **Amazon ECS Express Mode** como reemplazo directo,
> con la misma simplicidad operativa (una sola llamada de API → Fargate + ALB + auto
> scaling, sin servicios extra que administrar). Fuente:
> [App Runner availability change](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html).
> Por eso el camino primario de este proyecto pasó de App Runner a ECS Express Mode; App
> Runner queda documentado solo como opción para cuentas que ya tenían acceso.

### Camino A — Bedrock AgentCore Runtime (registro para puntaje del hackathon)

**Importante:** AgentCore Runtime **no puede servir la API real del producto**
(subida de archivos multipart, `GET /jobs/{id}`, `/ws/jobs`, `/backgrounds`, `/files`).
Su contrato de invocación en producción es la acción de AWS `bedrock-agentcore:InvokeAgentRuntime`
(SDK/CLI con IAM/SigV4, o HTTPS con OAuth) contra `/invocations` — JSON de entrada/salida,
sesión con `runtimeSessionId` — no una URL pública con ruteo a rutas arbitrarias. No hay
soporte de multipart en ese contrato, y no hay paso genérico de WebSocket para un navegador.
Registrarlo sigue siendo útil como demostración de integración real con Bedrock AgentCore
(y la imagen ya es multi-arch, así que el requisito ARM64 no cuesta nada extra) — pero el
tráfico real de la app pasa por el Camino B.

**Nota de arquitectura (ver `03-revision-tecnica.md`):** SnapFlick usa FastAPI como único
servidor (no la clase `BedrockAgentCoreApp`), así que el despliegue no pasa por el CLI
`agentcore configure`/`launch` (que espera un entrypoint basado en esa clase para generar
su propio Dockerfile) — en su lugar, se registra directamente el contenedor ya construido
y probado:

```bash
# 1) Construir y publicar la imagen multi-arch (ver sección 2.3 arriba)
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
`GET /ping`, y ahora también ARM64 (imagen multi-arch).

### Camino B (preferido) — Amazon ECS Express Mode

Reemplazo recomendado por AWS para App Runner: mismo contenedor, un solo comando, misma
simplicidad operativa (Fargate + Application Load Balancer + auto scaling, todo provisto
automáticamente).

```bash
aws ecs create-express-gateway-service \
  --execution-role-arn arn:aws:iam::$ACCOUNT:role/ecsTaskExecutionRole \
  --infrastructure-role-arn arn:aws:iam::$ACCOUNT:role/ecsInfrastructureRoleForExpressServices \
  --primary-container '{
      "image": "'"$ACCOUNT"'.dkr.ecr.'"$REGION"'.amazonaws.com/snapflick:latest",
      "containerPort": 8080
  }' \
  --service-name snapflick \
  --health-check-path "/ping" \
  --scaling-target '{"minTaskCount":1,"maxTaskCount":2}' \
  --region $REGION
```

El cpu/memoria de la tarea (ver medición real abajo: ~1.44 GiB de pico) se fija con el
parámetro correspondiente de `create-express-gateway-service` — confirmar el nombre exacto
del flag con `aws ecs create-express-gateway-service help` al momento de desplegar (no
verificado contra una cuenta real en este cambio), apuntando a **1 vCPU / 3–4 GB**.

Los dos roles IAM (`ecsTaskExecutionRole`, `ecsInfrastructureRoleForExpressServices`) son
prerequisito — ver
[Getting started with ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
para crearlos. El rol de tarea necesita `bedrock:InvokeModel` y, si se usa S3, acceso al
bucket. Variables de entorno: las de `.env.example`, pasadas en `environment` dentro de
`--primary-container`.

**⚠️ El ALB cobra por hora exista o no tráfico — leer la sección de costos antes de dejarlo
corriendo.**

#### Dimensionar cpu/memoria

Medido en vivo con `docker stats` contra el contenedor real (`make docker-build` + `docker run`,
imagen `linux/amd64`, un job real de una foto contra Gemini), no estimado:

| Momento | Memoria del contenedor |
|---|---|
| En reposo, recién arrancado (antes de `/warmup`) | ~62 MiB |
| Después de `/warmup` (modelo de rembg cargado + proveedor de IA resuelto) | ~860–867 MiB |
| Pico durante el procesamiento real de una imagen (rembg + composición + llamada a Gemini) | **~1.44 GiB** |

El salto grande es cargar el modelo ONNX de rembg en memoria (de ~62 MiB a ~860 MiB solo con
eso) — de ahí la importancia de pagar ese costo con `/warmup` antes de la demo en vez de en
el primer request real. El pico real durante el procesamiento (~1.44 GiB) es el número que
debe guiar el `cpu`/`memory` de `--primary-container`: de la
[tabla de configuraciones soportadas](https://docs.aws.amazon.com/apprunner/latest/dg/architecture.html#architecture.vcpu-memory)
(los mismos escalones que usa Fargate/ECS Express Mode), **1 vCPU / 3 GB o 1 vCPU / 4 GB**
deja margen razonable sobre ese pico; 2 GB se quedaría corto.

Para volver a medirlo (p.ej. tras cambiar el modelo de rembg o el tamaño de canvas):
```bash
make docker-build
docker run --rm -p 8080:8080 --env-file agent/.env --name snapflick-mem snapflick:local &
curl -X POST localhost:8080/warmup
# en otra terminal, mientras se procesa un job real (POST /jobs):
docker stats --no-stream snapflick-mem
```
`docker stats` (no `Get-Process`/`ps` sobre el proceso Python suelto) es lo correcto acá —
lo que hay que dimensionar es el contenedor completo (Python + sesión de rembg + onnxruntime
+ servidor), no solo el intérprete.

### Camino C (legado, solo cuentas con acceso previo) — AWS App Runner

Mismo contenedor, despliegue en pocos minutos desde la consola. Solo funciona si tu cuenta
ya tenía acceso a App Runner antes del cierre a clientes nuevos (ver nota al inicio de esta
sección).

1. Consola → **App Runner** → **Create service**.
2. Origen: **Container registry** → Amazon ECR → elegir `snapflick:latest`.
3. Puerto: `8080`. Health check: `/ping`.
4. Variables de entorno: las de `.env.example`.
5. Rol de instancia con permisos `bedrock:InvokeModel` y acceso al bucket S3.
6. Create & deploy → entrega una URL `https://xxxx.awsapprunner.com`.

App Runner cobra por hora de contenedor activo y **se puede pausar** (deja de facturar
cómputo mientras está pausado) — a diferencia de ECS Express Mode, donde el ALB sigue
cobrando aunque el servicio esté en cero tareas (ver costos).

### Frontend en Amplify Hosting
1. Consola → **AWS Amplify** → **Deploy an app** → GitHub → autorizar → elegir el repo.
2. **Monorepo:** marca la casilla y pon `web` como raíz de la app — `web/amplify.yml` ya
   trae la configuración de build (`npm ci` / `npm run build`, `appRoot: web`).
3. Variable de entorno `NEXT_PUBLIC_API_URL` = la URL de la API desplegada (ECS Express
   Mode/App Runner/AgentCore, según cuál uses). Ya está leída en el frontend
   (`web/src/lib/api.ts`) y documentada en `web/.env.example` — solo falta setearla en la
   consola de Amplify.
4. Save and deploy. Cada push a `main` redespliega automáticamente.

---

## 3.1 Apagar todo entre sesiones de demo (ECS Express Mode)

**Escalar el servicio a cero tareas NO detiene el cobro del ALB.** El único camino a costo
cero es borrar el servicio:

```bash
infra/scripts/teardown.sh <service-arn-de-express-mode>
```

Esto llama a `aws ecs delete-express-gateway-service`, que borra el servicio y "el
Application Load Balancer (si ningún otro servicio lo usa), el target group, el security
group, el listener y la regla del listener", además de las políticas de auto scaling y el
cluster si queda vacío — ver
[Delete Amazon ECS Express Mode services](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-delete-task.html).
Bórralo después de cada grabación y en cuanto termine el hackathon; volver a crearlo con
`aws ecs create-express-gateway-service` toma minutos.

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
| **ALB de ECS Express Mode — cobra por hora exista o no tráfico** (~USD 0.0225/h, [pricing oficial](https://aws.amazon.com/elasticloadbalancing/pricing/)) | ~USD 16/mes si se deja corriendo — **borrar el servicio entre usos con `infra/scripts/teardown.sh`** |
| App Runner (legado, se puede pausar) o AgentCore (facturado por invocación) | USD 5–15 si se usa en vez de/además de ECS Express Mode |
| Amplify Hosting | Gratis en capa gratuita |
| **Total (con ECS Express Mode borrado entre sesiones)** | **USD 10–25** |

**Importante:** a diferencia de App Runner (que se pausa y deja de facturar cómputo), el ALB
que crea ECS Express Mode cobra por hora **aunque el servicio esté escalado a cero tareas y
sin tráfico**. Escalar a cero no es suficiente para llegar a costo cero — hay que borrar el
servicio (`infra/scripts/teardown.sh <service-arn>`) entre sesiones de grabación/demo y en
cuanto termine el hackathon. Dejar el servicio corriendo todo un mes agotaría buena parte del
presupuesto de USD 20–25 solo en el ALB.
