#!/usr/bin/env bash
# Construye y publica la imagen ARM64 en ECR. Ejecutar desde la raiz del repo.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
REPO="${ECR_REPO:-snapflick}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO"

aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

docker buildx create --use --name snapflick-builder 2>/dev/null || true
docker buildx build --platform linux/arm64 -t "$URI:latest" --push ./agent

echo "Imagen publicada: $URI:latest"
