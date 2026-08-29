#!/usr/bin/env bash
# Borra un servicio de Amazon ECS Express Mode y TODA su infraestructura
# asociada (ALB, target group, security group, listener, auto scaling, y el
# cluster si no lo usa nada mas). Escalar el servicio a cero tareas NO detiene
# el cobro por hora del ALB -- solo borrar el servicio lo hace.
# Ver docs/02-guia-despliegue-aws.md, seccion de costos.
set -euo pipefail

SERVICE_ARN="${1:?Uso: teardown.sh <service-arn-de-express-mode>}"
REGION="${AWS_REGION:-us-east-1}"

aws ecs delete-express-gateway-service --service-arn "$SERVICE_ARN" --region "$REGION"

echo "Servicio Express Mode eliminado (incluye ALB, target group y demas recursos exclusivos)."
