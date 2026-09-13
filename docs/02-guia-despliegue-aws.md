# Guía de despliegue en AWS

Guía técnica paso a paso para desplegar SnapFlick en una cuenta de AWS nueva. Asume cero
experiencia previa con AWS. Sigue las secciones en orden — cada una asume que la anterior ya
quedó lista.

## 0. Checklist previo

Verifica esto antes de tocar la consola. Si algo falta, resuélvelo primero; no tiene sentido
avanzar sin ello.

- [x] **AWS CLI configurado.** `aws sts get-caller-identity` debe devolver un JSON con
      `Account` y un `Arn` reconocible (el usuario/rol con el que vas a trabajar). Si da error
      de credenciales, corre `aws configure` antes de seguir (ver sección 1.6).
- [ ] **Docker instalado y corriendo:** `docker ps` no debe dar error.
- [ ] **Una sola región en todo el proceso:** `us-east-1` (ver 1.4 — no la cambies a mitad de
      camino).
- [ ] **API key del proveedor de modelo a mano** (p. ej. `SNAPFLICK_GEMINI_API_KEY`, ver
      `agent/.env.example`).
- [ ] **`.env` en `.gitignore` y ninguna credencial commiteada.**
- [ ] **Si el repo va a pasar a público en algún momento** (requisito común en hackathons):
      hacerlo público republica **todo el historial de git**, no solo el estado actual. Borrar
      una clave después no la quita del historial. Antes de cambiar la visibilidad, revisa:
      ```bash
      git log -p | grep -iE "secret|aws_access|api_key|BEGIN (RSA|OPENSSH) PRIVATE KEY"
      ```
      Si algo aparece, hay que rotar esa credencial y reescribir el historial (o empezar un
      repo limpio) antes de publicarlo — no basta con un commit nuevo que la borre.

Dos variables que se repiten en toda la guía. Defínelas una vez por sesión de terminal:

```bash
export REGION=us-east-1
export ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo $ACCOUNT
```

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

**Prerequisito de red:** Express Mode crea el balanceador en el VPC *default* de la cuenta.
Casi toda cuenta nueva ya tiene uno; confirma con:
```bash
aws ec2 describe-vpcs --filters Name=is-default,Values=true --region $REGION --query 'Vpcs[0].VpcId'
```
Si devuelve `null`, créalo con `aws ec2 create-default-vpc --region $REGION` antes de seguir
(o pasa tus propias subnets al crear el servicio — no cubierto aquí).

#### Paso 0 — Crear los tres roles IAM (una sola vez por cuenta)

Express Mode exige **dos** roles para poder crear el servicio, y el proyecto necesita un
**tercero** para que el contenedor pueda leer/escribir en S3 (y llamar a Bedrock si se usa ese
proveedor). Los tres se crean una única vez; los redespliegues posteriores los reutilizan.

```bash
# 1) Rol de ejecución de tarea (ECS descarga la imagen de ECR y escribe logs en tu nombre)
aws iam create-role --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# 2) Rol de infraestructura (permite a Express Mode crear el ALB, target group,
#    security group y auto scaling por ti)
aws iam create-role --role-name ecsInfrastructureRoleForExpressServices \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "AllowAccessInfrastructureForECSExpressServices",
      "Effect": "Allow",
      "Principal": {"Service": "ecs.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
aws iam attach-role-policy --role-name ecsInfrastructureRoleForExpressServices \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices

# 3) Rol de tarea (el código de la app: acceso a S3 y, si se usa Bedrock, a InvokeModel)
#    Reemplaza snapflick-<algo-unico> por el nombre real del bucket (ver sección 2.1)
aws iam create-role --role-name SnapFlickTaskRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
aws iam put-role-policy --role-name SnapFlickTaskRole --policy-name SnapFlickAppAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
        "Resource": [
          "arn:aws:s3:::snapflick-<algo-unico>",
          "arn:aws:s3:::snapflick-<algo-unico>/*"
        ]
      },
      {
        "Effect": "Allow",
        "Action": "bedrock:InvokeModel",
        "Resource": "*"
      }
    ]
  }'
```

**Nota de AWS:** los roles IAM son "eventually consistent" — si el primer
`create-express-gateway-service` falla con un error de tipo *"Unable to assume role"* justo
después de crearlos, espera un minuto y reintenta; no es un error de configuración.

Guarda los tres ARNs (los necesitas en el paso siguiente):
```bash
export EXEC_ROLE_ARN=$(aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.Arn' --output text)
export INFRA_ROLE_ARN=$(aws iam get-role --role-name ecsInfrastructureRoleForExpressServices --query 'Role.Arn' --output text)
export TASK_ROLE_ARN=$(aws iam get-role --role-name SnapFlickTaskRole --query 'Role.Arn' --output text)
```

#### Paso 1 — Crear el servicio

Pasa las variables de `agent/.env.example` con sus **nombres exactos** (un nombre mal escrito
no da error: `Settings` ignora las variables desconocidas y el valor por defecto del código
queda vigente en silencio — p. ej. `SNAPFLICK_MODEL_ID` no existe, el nombre real es
`SNAPFLICK_GEMINI_MODEL_ID`).

**`SNAPFLICK_CORS_ORIGINS` es obligatoria en producción desde que el backend usa sesiones
anónimas por cookie** (`sf_session`, ver `main.py`). El default del código es
`http://localhost:3000` — sin esta variable seteada a la URL real del frontend, el navegador
rechaza la cookie de sesión (CORS con `allow_credentials=True` no acepta `*` como origen) y
cada usuario pierde sus jobs entre requests. Ponla igual a la URL de Amplify Hosting (o al
dominio propio del frontend si ya lo conectaste, sección "Dominio propio para el frontend").
Acepta varios orígenes separados por coma si necesitas más de uno (ej. producción + preview).

**⚠️ Si tu terminal es Git Bash (el que instala "Git para Windows") — confirmado en vivo:**
Git Bash convierte automáticamente cualquier argumento que empiece con `/` a una ruta de
Windows, así que `--health-check-path "/ping"` te llega a AWS como
`"C:/Program Files/Git/ping"` — el servicio se crea, el ALB se factura, pero se queda
atascado para siempre en `PROVISIONING` con
`ValidationError: Health check path '...' must begin with a '/' character`. Anteponer
`MSYS_NO_PATHCONV=1` al comando desactiva esa conversión solo para esa llamada (no hace falta
en PowerShell/cmd.exe, solo en Git Bash/MSYS).

```bash
MSYS_NO_PATHCONV=1 aws ecs create-express-gateway-service \
  --execution-role-arn $EXEC_ROLE_ARN \
  --infrastructure-role-arn $INFRA_ROLE_ARN \
  --task-role-arn $TASK_ROLE_ARN \
  --primary-container '{
      "image": "'"$ACCOUNT"'.dkr.ecr.'"$REGION"'.amazonaws.com/snapflick:latest",
      "containerPort": 8080,
      "environment": [
        {"name": "SNAPFLICK_MODEL_PROVIDER", "value": "gemini"},
        {"name": "SNAPFLICK_GEMINI_API_KEY", "value": "TU_API_KEY_AQUI"},
        {"name": "SNAPFLICK_GEMINI_MODEL_ID", "value": "gemini-2.5-flash-lite"},
        {"name": "SNAPFLICK_S3_BUCKET", "value": "snapflick-<algo-unico>"},
        {"name": "SNAPFLICK_AWS_REGION", "value": "'"$REGION"'"},
        {"name": "SNAPFLICK_LOG_LEVEL", "value": "INFO"},
        {"name": "SNAPFLICK_CORS_ORIGINS", "value": "https://main.d3mxnoo9ebk8qj.amplifyapp.com"}
      ]
  }' \
  --service-name snapflick \
  --health-check-path "/ping" \
  --cpu 1024 \
  --memory 4096 \
  --scaling-target '{"minTaskCount":1,"maxTaskCount":2}' \
  --region $REGION \
  --monitor-resources
```

**`--cpu`/`--memory` van en las unidades clásicas de Fargate, no en vCPU/GB enteros** —
`--cpu` es unidades de CPU (`256` = .25 vCPU, `1024` = 1 vCPU) y `--memory` es **MiB**, no GB
(confirmado en vivo: `--cpu 1 --memory 4` falla con `InvalidParameterException: Invalid
CPU/Memory combination`, porque eso pide casi nada de CPU y 4 MiB de RAM). `--cpu 1024
--memory 4096` da 1 vCPU / 4 GiB, con margen holgado sobre el pico real medido más abajo
(~1.44 GiB). Para 1024 CPU units, la memoria válida va de 2048 a 8192 MiB en pasos de 1024
(2/3/4/5/6/7/8 GB) — `3072` también serviría si prefieres 3 GB. **No pongas
`AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY`** en `environment` — esas llegan por
`SnapFlickTaskRole`.

`--monitor-resources` deja el comando esperando y mostrando el progreso hasta que el servicio
queda `ACTIVE`; al terminar imprime el `serviceArn` y la URL — **anota el `serviceArn`**, lo
necesitas para `infra/scripts/teardown.sh` en la sección 3.1. Si prefieres no esperar, quita
la flag y consulta el estado después con:
```bash
aws ecs describe-express-gateway-service --service-arn <arn-que-guardaste> --region $REGION
```

**¿Cuánto tarda?** Sin errores de configuración, entre **3 y 8 minutos** — AWS tiene que
crear el ALB, el certificado TLS, el target group y arrancar la tarea de Fargate (descargar
la imagen + levantar el contenedor). Si pasan más de 10-15 minutos sin llegar a `ACTIVE`, algo
está mal (revisa el `Reason` de cada recurso en la salida de `--monitor-resources`, o corre el
`describe` de arriba) — no es normal que tarde una media hora como con el error del health
check.

Antes de dar la URL por buena, caliéntala una vez — `/ping` responde al instante pero
**no** carga nada (es el health check); el que precarga rembg y resuelve el proveedor de IA es
`/warmup`:
```bash
curl -X POST https://<url-del-servicio>/warmup
```

**⚠️ El ALB cobra por hora exista o no tráfico.** Como el `service-name` de este proyecto es
siempre `snapflick` en el cluster `default`, el ARN es predecible — no hace falta ir a buscarlo
cada vez. Para apagar todo antes de dormir/entre sesiones (con `$REGION`/`$ACCOUNT` ya
exportados desde la sección 0):
```bash
aws ecs delete-express-gateway-service \
  --service-arn arn:aws:ecs:$REGION:$ACCOUNT:service/default/snapflick \
  --region $REGION
```
Confirma que quedó borrado (no solo "aceptado") antes de cerrar la laptop:
```bash
aws ecs describe-express-gateway-service \
  --service-arn arn:aws:ecs:$REGION:$ACCOUNT:service/default/snapflick \
  --region $REGION --query 'service.status.statusCode' --output text
```
Tarda uno o dos minutos en pasar de `DRAINING` a `INACTIVE` (o a no encontrarse, "ServiceNotFoundException" — ambos significan que ya no cobra). Ver también la sección 3.1 más abajo.

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
deja margen razonable sobre ese pico; 2 GB se quedaría corto. Al pasarlo al comando de la
sección anterior, recuerda que `--cpu`/`--memory` de `create-express-gateway-service` no
aceptan "1" y "4" — van en unidades de Fargate: `--cpu 1024 --memory 3072` (3 GB) o
`--cpu 1024 --memory 4096` (4 GB).

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

**⚠️ Trampa confirmada en vivo: el primer build puede "tener éxito" sin construir nada.**
Al marcar la casilla de monorepo, Amplify agrega por su cuenta la variable de entorno
`AMPLIFY_DIFF_DEPLOY=true` (optimización que solo reconstruye si detecta cambios dentro de
`web/` respecto al despliegue anterior). En el **primer** despliegue no hay despliegue
anterior con qué comparar, esa lógica concluye igual "sin cambios", y te deja con:
```
# No differences detected.
## Skipping Frontend Build & Deploy, No changes detected...
# The frontend build was skipped. Deployment will be skipped as well.
```
— el job queda en `SUCCEED` (porque no falló, simplemente no hizo nada) y la URL sirve la
página de bienvenida por defecto de Amplify en vez de tu app. Es un comportamiento conocido de
`AMPLIFY_DIFF_DEPLOY` en primeros despliegues (ver
[issue relacionado en aws-amplify/amplify-hosting](https://github.com/aws-amplify/amplify-hosting/issues/3268)),
no un error tuyo de configuración.

**Arreglo:**
1. Consola → tu app de Amplify → **App settings** → **Environment variables** → borra
   `AMPLIFY_DIFF_DEPLOY` (o ponla en `false`). Deja `AMPLIFY_MONOREPO_APP_ROOT` y
   `NEXT_PUBLIC_API_URL` como están.
2. Dispara un build nuevo — **"Redeploy this version" no sirve** (repite la misma evaluación
   cacheada); usa **"Start new deployment"**, o simplemente haz un nuevo `git push` a `main`.
3. Confirma que ahora sí compiló (el log de build ya no debe decir "Skipping Frontend Build").

### Dominio propio para el frontend (opcional)

A diferencia del backend en ECS Express Mode (sección 5, mucho más manual), Amplify Hosting
tiene soporte nativo para dominio personalizado — no hay que tocar ningún ALB a mano.

1. Tu app de Amplify → pestaña **Hosting** (o el panel **"Pasar a producción"**) →
   **Agregar dominio personalizado**.
2. Escribe tu dominio o subdominio (p. ej. `app.tudominio.com` o `snapflick.tudominio.com`).
3. Elige **"DNS provider is not Route 53"** (tu dominio vive en tu registrador externo) —
   Amplify te da los registros CNAME de validación y de enrutamiento.
4. Copia esos registros CNAME en el panel de tu registrador.
5. Amplify emite el certificado SSL solo (gratis) y activa el dominio cuando el DNS valida —
   puede tardar de minutos a un par de horas.

Si el backend también tiene dominio propio (sección 5), usa un subdominio distinto para cada
uno — p. ej. `app.tudominio.com` para el frontend y `api.tudominio.com` para el backend — y
actualiza `NEXT_PUBLIC_API_URL` en Amplify para que apunte al subdominio del backend en vez de
la URL `on.aws`.

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

- [ ] El servicio de ECS Express Mode **existe y está `ACTIVE`** (no borrado por el
      checklist de costos de la sección 3.1 — un servicio borrado devuelve error y la URL
      queda inservible).
- [ ] Se hizo un `curl -X POST <url>/warmup` reciente — si no, la primera visita real paga
      el costo de cargar rembg (~800 ms extra) y de resolver el proveedor de IA.
- [ ] La URL responde desde una red distinta a la de desarrollo (p. ej. datos móviles, no
      solo el wifi de casa).
- [ ] Repo público: se revisó **todo el historial** de git por secretos, no solo el estado
      actual (ver checklist previo, sección 0).
- [ ] La alerta de presupuesto no se ha disparado.
- [ ] CORS, límites de tamaño de archivo y timeouts están configurados razonablemente.

---

## 5. Dominio propio para el backend (opcional)

La URL que te da Express Mode (`sn-xxxx.ecs.us-east-1.on.aws`) funciona perfecto pero no es
memorable. Express Mode **no tiene un parámetro para dominio personalizado** — hay que
configurar el ALB que ya creó por debajo, a mano. Confirmado contra la documentación oficial
de AWS (["Adding a custom domain to your service"](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-advanced-customization.html#express-service-add-custom-domain));
lo que sigue es esa misma guía adaptada a un dominio en un registrador externo (no Route 53),
que es el caso típico de un dominio comprado en Namecheap/GoDaddy/etc.

**⚠️ Léelo completo antes de empezar — hay una trampa con el apagado entre sesiones (sección
3.1) que vale la pena decidir de antemano.** Ver el aviso al final de esta sección.

### 5.1 Pedir el certificado ACM (en la misma región del ALB, `us-east-1`)

```bash
aws acm request-certificate \
  --domain-name api.tudominio.com \
  --validation-method DNS \
  --region us-east-1
```

Guarda el ARN que devuelve, y pide el registro CNAME de validación:
```bash
export CERT_ARN=<arn-que-te-dio-el-comando-anterior>
aws acm describe-certificate --certificate-arn $CERT_ARN --region us-east-1 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```
Copia el `Name` y `Value` que imprime y créalos como registro **CNAME** en tu registrador
(no en la consola de AWS — tu dominio no vive ahí). Cuando lo hayas puesto, espera a que
valide (puede tardar de minutos a un par de horas):
```bash
aws acm wait certificate-validated --certificate-arn $CERT_ARN --region us-east-1
```
El comando se queda esperando hasta que el estado pase a `ISSUED`.

### 5.2 Editar la regla del listener y agregar el certificado (por consola)

Este paso es de consola porque así lo documenta AWS oficialmente — edita una regla existente
con condiciones OR, que es más seguro hacer con el asistente visual que a ciegas por CLI:

1. Consola → **ECS** → **Clusters** → `default` → pestaña **Services** → `snapflick` →
   pestaña **Resources** → selecciona la **listener rule**.
2. **Action** → **Edit Rule**.
3. Copia el valor actual de la condición **Host header** (tu URL `on.aws`) — anótalo, lo
   necesitas en el siguiente paso.
4. **Remove** la regla (Express Mode solo permite una regla de cada tipo, así que hay que
   quitarla para poder editar las condiciones).
5. Agrega una condición tipo **Host header**, pega de nuevo tu URL `on.aws` como valor.
6. Click **Add OR condition value** → escribe tu dominio propio (`api.tudominio.com`).
7. **Next** → **Save changes**.
8. Ve a la pestaña **Certificates** del listener del ALB → **Add certificate** → selecciona
   el certificado ACM que ya quedó `ISSUED` en el paso 5.1.

### 5.3 Apuntar tu dominio al ALB

En tu registrador, crea un **CNAME**:
```
api.tudominio.com  →  ecs-express-gateway-alb-xxxx.us-east-1.elb.amazonaws.com
```
(el nombre del ALB, no la URL `on.aws` — lo ves en la consola de EC2 → Load Balancers, o con
`aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[].DNSName'`).
Después de unos minutos de propagación, `https://api.tudominio.com/ping` debería responder
igual que la URL `on.aws`.

### ⚠️ La trampa: esto no sobrevive un `delete` + `create`

`delete-express-gateway-service` borra el ALB completo — con él, la regla y el certificado
que acabas de agregar a mano. Si vuelves a crear el servicio, Express Mode arma un ALB
**nuevo** desde cero, sin tu dominio conectado. El certificado ACM del paso 5.1 sí sobrevive
(es un recurso aparte) y se reutiliza, pero los pasos 5.2 y 5.3 (rehacer la regla, re-adjuntar
el certificado) hay que repetirlos cada vez.

Dos caminos, elige uno a propósito:
- **Quieres una URL de dominio propio estable** (para dar la URL final a los jueces, por
  ejemplo): deja el servicio corriendo sin borrarlo entre sesiones y asume el costo fijo del
  ALB (~USD 16-18/mes, ver "Costos estimados" abajo).
- **Prefieres seguir apagando entre sesiones** (sección 3.1) para no pagar de más: acepta que
  cada vez que recrees el servicio hay que repetir 5.2 y 5.3 (5-10 minutos, sin volver a pedir
  el certificado).

Además, AWS advierte explícitamente que **Express Mode no protege tus cambios manuales de
conflictos futuros**: si más adelante corres `update-express-gateway-service` tocando algo
que tenga que ver con el listener o el health check, podría pisar la regla o el certificado
que agregaste a mano. Después de cualquier `update`, vale la pena volver a probar
`https://api.tudominio.com/ping` para confirmar que el dominio sigue funcionando.

---

## 6. Redesplegar (ciclo normal, cuando ya hay código nuevo en la rama)

**Frontend:** nada que hacer a mano — cada `git push` a `main` dispara el build de Amplify
solo (webhook ya conectado desde la sección "Frontend en Amplify Hosting").

**Backend: siempre manual.** ECS Express Mode no vigila el tag `:latest` de ECR — aunque subas
una imagen nueva, las tareas que ya están corriendo no se enteran solas. Hay que:

### 6.1 Reconstruir y publicar la imagen
```bash
infra/scripts/deploy.sh
```
(o el `docker buildx build --platform linux/amd64,linux/arm64 ... --push ./agent` de la
sección 2.3, a mano).

### 6.2 Actualizar el servicio para que tome la imagen nueva

```bash
aws ecs update-express-gateway-service \
  --service-arn arn:aws:ecs:$REGION:$ACCOUNT:service/default/snapflick \
  --primary-container '{
      "image": "'"$ACCOUNT"'.dkr.ecr.'"$REGION"'.amazonaws.com/snapflick:latest",
      "containerPort": 8080,
      "environment": [
        {"name": "SNAPFLICK_MODEL_PROVIDER", "value": "gemini"},
        {"name": "SNAPFLICK_GEMINI_API_KEY", "value": "TU_API_KEY"},
        {"name": "SNAPFLICK_GEMINI_MODEL_ID", "value": "gemini-flash-latest"},
        {"name": "SNAPFLICK_S3_BUCKET", "value": "snapflick-gode-2026"},
        {"name": "SNAPFLICK_AWS_REGION", "value": "'"$REGION"'"},
        {"name": "SNAPFLICK_LOG_LEVEL", "value": "INFO"}
      ]
  }' \
  --region $REGION \
  --monitor-resources
```

**⚠️ La lista `environment` se reemplaza completa, no se fusiona con la anterior.** Si omites
una variable que ya estaba puesta, esa variable desaparece del contenedor en el próximo
despliegue — no queda "la de antes" por defecto. Cada vez que actualices, copia la lista
completa vigente (revísala con el `describe` de abajo si no la tienes a mano) y agrégale o
quítale lo que corresponda; nunca mandes solo la variable nueva sola.

**Si necesitas agregar una variable nueva** (por ejemplo `SNAPFLICK_CORS_ORIGINS` cuando el
backend empiece a depender de cookies de sesión y CORS deje de poder ser `*`), es el mismo
comando: la lista completa de `environment` con la variable nueva añadida.

Para ver qué está corriendo *ahora mismo* antes de armar el `environment` completo:
```bash
aws ecs describe-express-gateway-service \
  --service-arn arn:aws:ecs:$REGION:$ACCOUNT:service/default/snapflick \
  --region $REGION \
  --query 'service.activeConfigurations[0].primaryContainer.environment'
```

### 6.3 Confirmar y calentar
Igual que en el primer despliegue (sección "Paso 1"): espera a `ACTIVE`/`SUCCESSFUL` y llama
a `/warmup` antes de dar la URL por buena.

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
