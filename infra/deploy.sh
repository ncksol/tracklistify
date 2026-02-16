#!/usr/bin/env bash
set -euo pipefail

# Default values
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-tracklistify}"
LOCATION="${LOCATION:-uksouth}"

# Required parameters
if [ -z "${DB_ADMIN_LOGIN:-}" ]; then
  echo "Error: DB_ADMIN_LOGIN environment variable is required"
  exit 1
fi

if [ -z "${DB_ADMIN_PASSWORD:-}" ]; then
  echo "Error: DB_ADMIN_PASSWORD environment variable is required"
  exit 1
fi

# Resource group name
RESOURCE_GROUP="rg-${ENVIRONMENT_NAME}"

echo "========================================="
echo "Deploying Tracklistify Infrastructure"
echo "========================================="
echo "Environment:    ${ENVIRONMENT_NAME}"
echo "Location:       ${LOCATION}"
echo "Resource Group: ${RESOURCE_GROUP}"
echo "========================================="

# Step 1: Create resource group
echo ""
echo "[1/5] Creating resource group..."
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}"

# Step 2: Deploy main.bicep (Container Apps Environment + Log Analytics)
echo ""
echo "[2/5] Deploying Container Apps Environment and Log Analytics..."
MAIN_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/main.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
  --query 'properties.outputs' \
  --output json)

CONTAINER_ENV_ID=$(echo "${MAIN_OUTPUT}" | jq -r '.containerAppsEnvironmentId.value')
echo "✓ Container Apps Environment ID: ${CONTAINER_ENV_ID}"

# Step 3: Deploy database.bicep (PostgreSQL)
echo ""
echo "[3/5] Deploying PostgreSQL database..."
DB_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/database.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
    administratorLogin="${DB_ADMIN_LOGIN}" administratorPassword="${DB_ADMIN_PASSWORD}" \
  --query 'properties.outputs' \
  --output json)

DB_FQDN=$(echo "${DB_OUTPUT}" | jq -r '.fqdn.value')
DB_NAME=$(echo "${DB_OUTPUT}" | jq -r '.databaseName.value')
echo "✓ PostgreSQL FQDN: ${DB_FQDN}"
echo "✓ Database Name: ${DB_NAME}"

# Step 4: Deploy redis.bicep (Redis)
echo ""
echo "[4/5] Deploying Redis cache..."
REDIS_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/redis.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
  --query 'properties.outputs' \
  --output json)

REDIS_HOSTNAME=$(echo "${REDIS_OUTPUT}" | jq -r '.hostName.value')
REDIS_PORT=$(echo "${REDIS_OUTPUT}" | jq -r '.sslPort.value')
REDIS_KEY=$(echo "${REDIS_OUTPUT}" | jq -r '.primaryKey.value')
echo "✓ Redis Hostname: ${REDIS_HOSTNAME}"

# Step 5: Deploy storage.bicep (Blob Storage)
echo ""
echo "[5/5] Deploying Blob Storage..."
STORAGE_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/storage.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
  --query 'properties.outputs' \
  --output json)

STORAGE_ACCOUNT=$(echo "${STORAGE_OUTPUT}" | jq -r '.storageAccountName.value')
BLOB_ENDPOINT=$(echo "${STORAGE_OUTPUT}" | jq -r '.blobEndpoint.value')
echo "✓ Storage Account: ${STORAGE_ACCOUNT}"
echo "✓ Blob Endpoint: ${BLOB_ENDPOINT}"

# Build connection strings
DATABASE_URL="postgresql://${DB_ADMIN_LOGIN}:${DB_ADMIN_PASSWORD}@${DB_FQDN}/${DB_NAME}?sslmode=require"
REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOSTNAME}:${REDIS_PORT}/0"

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Deployed Resources:"
echo "-------------------"
echo "Resource Group:    ${RESOURCE_GROUP}"
echo "Container Apps Env: ${CONTAINER_ENV_ID}"
echo "PostgreSQL Server: ${DB_FQDN}"
echo "Redis Cache:       ${REDIS_HOSTNAME}:${REDIS_PORT}"
echo "Storage Account:   ${STORAGE_ACCOUNT}"
echo ""
echo "Connection Strings (save these securely):"
echo "------------------------------------------"
echo "DATABASE_URL: ${DATABASE_URL}"
echo "REDIS_URL:    ${REDIS_URL}"
echo ""
echo "Note: Container apps deployment (infra/containers.bicep) requires additional parameters:"
echo "  - acrName (Azure Container Registry name)"
echo "  - acrcloudAccessKey, acrcloudAccessSecret, acrcloudHost"
echo "  - secretKey"
echo "  - corsOrigins (optional)"
echo "  - Image tags (backendImageTag, celeryImageTag, frontendImageTag)"
echo ""
echo "Deploy containers manually once images are built and pushed to ACR."
echo "========================================="
