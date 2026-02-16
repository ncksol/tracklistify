#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Tracklistify Passwordless Deployment Script
# ============================================================================
# This script deploys the complete Tracklistify infrastructure to Azure
# using passwordless authentication (Managed Identity + Entra ID) for all
# Azure services: PostgreSQL, Redis, Storage, and Key Vault.
# ============================================================================

# Default values
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-tracklistify}"
LOCATION="${LOCATION:-uksouth}"
DB_ADMIN_LOGIN="${DB_ADMIN_LOGIN:-tracklistifyadmin}"
ACR_HOST="${ACR_HOST:-identify-eu-west-1.acrcloud.com}"

# Required environment variables validation
if [ -z "${ACR_ACCESS_KEY:-}" ]; then
  echo "Error: ACR_ACCESS_KEY environment variable is required"
  exit 1
fi

if [ -z "${ACR_ACCESS_SECRET:-}" ]; then
  echo "Error: ACR_ACCESS_SECRET environment variable is required"
  exit 1
fi

# Generate random DB admin password if not provided (still required by Azure API)
DB_ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:-$(openssl rand -base64 24)}"

# Derived values
RESOURCE_GROUP="rg-${ENVIRONMENT_NAME}"
ACR_NAME=$(echo "${ENVIRONMENT_NAME}acr" | tr -d '-' | tr '[:upper:]' '[:lower:]')

echo "============================================================================"
echo "Tracklistify Passwordless Deployment"
echo "============================================================================"
echo "Environment:    ${ENVIRONMENT_NAME}"
echo "Location:       ${LOCATION}"
echo "Resource Group: ${RESOURCE_GROUP}"
echo "ACR Name:       ${ACR_NAME}"
echo "============================================================================"
echo ""

# Step 1: Get logged-in user info for Entra ID admin
echo "[Step 1/14] Getting logged-in user information..."
USER_INFO=$(az ad signed-in-user show --query '{objectId:id, displayName:displayName}' --output json)
USER_OBJECT_ID=$(echo "${USER_INFO}" | jq -r '.objectId')
USER_DISPLAY_NAME=$(echo "${USER_INFO}" | jq -r '.displayName')
echo "✓ User Object ID: ${USER_OBJECT_ID}"
echo "✓ Display Name: ${USER_DISPLAY_NAME}"
echo ""

# Step 2: Create resource group
echo "[Step 2/14] Creating resource group..."
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}" \
  --output none
echo "✓ Resource group created: ${RESOURCE_GROUP}"
echo ""

# Step 3: Deploy main.bicep (Container Apps Environment + Log Analytics)
echo "[Step 3/14] Deploying Container Apps Environment..."
MAIN_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/main.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
  --query 'properties.outputs' \
  --output json)

CONTAINER_ENV_ID=$(echo "${MAIN_OUTPUT}" | jq -r '.containerAppsEnvironmentId.value')
echo "✓ Container Apps Environment ID: ${CONTAINER_ENV_ID}"
echo ""

# Step 4: Deploy database.bicep with Entra admin
echo "[Step 4/14] Deploying PostgreSQL with Entra ID authentication..."
DB_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/database.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
    administratorLogin="${DB_ADMIN_LOGIN}" administratorPassword="${DB_ADMIN_PASSWORD}" \
    entraAdminObjectId="${USER_OBJECT_ID}" entraAdminName="${USER_DISPLAY_NAME}" \
    entraAdminType="User" \
  --query 'properties.outputs' \
  --output json)

DB_FQDN=$(echo "${DB_OUTPUT}" | jq -r '.fqdn.value')
DB_NAME=$(echo "${DB_OUTPUT}" | jq -r '.databaseName.value')
DB_SERVER_NAME=$(echo "${DB_OUTPUT}" | jq -r '.serverName.value')
echo "✓ PostgreSQL FQDN: ${DB_FQDN}"
echo "✓ Database Name: ${DB_NAME}"
echo "✓ Entra ID Admin configured: ${USER_DISPLAY_NAME}"
echo ""

# Step 5: Deploy redis.bicep
echo "[Step 5/14] Deploying Redis cache..."
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
echo "✓ Redis Port: ${REDIS_PORT}"
echo ""

# Step 6: Deploy storage.bicep
echo "[Step 6/14] Deploying Blob Storage..."
STORAGE_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/storage.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
  --query 'properties.outputs' \
  --output json)

STORAGE_ACCOUNT=$(echo "${STORAGE_OUTPUT}" | jq -r '.storageAccountName.value')
echo "✓ Storage Account: ${STORAGE_ACCOUNT}"
echo ""

# Step 7: Deploy keyvault.bicep with ACRCloud secrets
echo "[Step 7/14] Deploying Key Vault with ACRCloud secrets..."
KV_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/keyvault.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
    acrcloudAccessKey="${ACR_ACCESS_KEY}" acrcloudAccessSecret="${ACR_ACCESS_SECRET}" \
    acrcloudHost="${ACR_HOST}" \
  --query 'properties.outputs' \
  --output json)

KEY_VAULT_URI=$(echo "${KV_OUTPUT}" | jq -r '.keyVaultUri.value')
KEY_VAULT_NAME=$(echo "${KV_OUTPUT}" | jq -r '.keyVaultName.value')
echo "✓ Key Vault URI: ${KEY_VAULT_URI}"
echo "✓ Key Vault Name: ${KEY_VAULT_NAME}"

# Store Redis primary key in Key Vault (for Celery broker)
echo "  - Storing Redis key in Key Vault..."
az keyvault secret set \
  --vault-name "${KEY_VAULT_NAME}" \
  --name "redis-primary-key" \
  --value "${REDIS_KEY}" \
  --output none
echo "✓ Redis key stored in Key Vault"
echo ""

# Step 8: Create Azure Container Registry (idempotent)
echo "[Step 8/14] Creating Azure Container Registry..."
az acr create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${ACR_NAME}" \
  --sku Basic \
  --location "${LOCATION}" \
  --admin-enabled false \
  --output none 2>/dev/null || echo "✓ ACR already exists: ${ACR_NAME}"
echo "✓ Azure Container Registry: ${ACR_NAME}"
echo ""

# Step 9: Build and push backend Docker image
echo "[Step 9/14] Building and pushing backend Docker image..."
az acr build \
  --registry "${ACR_NAME}" \
  --image tracklistify-backend:latest \
  --file backend/Dockerfile \
  backend/
echo "✓ Backend image pushed to ACR"
echo ""

# Step 10: Deploy containers with passwordless configuration
echo "[Step 10/14] Deploying container apps (backend, celery, frontend)..."
CONTAINER_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/containers.bicep \
  --parameters location="${LOCATION}" environmentName="${ENVIRONMENT_NAME}" \
    containerAppsEnvironmentId="${CONTAINER_ENV_ID}" \
    acrName="${ACR_NAME}" \
    postgresHost="${DB_FQDN}" \
    postgresDatabase="${DB_NAME}" \
    redisHost="${REDIS_HOSTNAME}" \
    storageAccountName="${STORAGE_ACCOUNT}" \
    keyVaultUri="${KEY_VAULT_URI}" \
    corsOrigins="*" \
  --query 'properties.outputs' \
  --output json)

BACKEND_FQDN=$(echo "${CONTAINER_OUTPUT}" | jq -r '.backendFqdn.value')
FRONTEND_FQDN=$(echo "${CONTAINER_OUTPUT}" | jq -r '.frontendFqdn.value')
BACKEND_PRINCIPAL_ID=$(echo "${CONTAINER_OUTPUT}" | jq -r '.backendPrincipalId.value')
CELERY_PRINCIPAL_ID=$(echo "${CONTAINER_OUTPUT}" | jq -r '.celeryPrincipalId.value')
echo "✓ Backend FQDN: ${BACKEND_FQDN}"
echo "✓ Frontend FQDN: ${FRONTEND_FQDN}"
echo ""

# Step 11: Assign RBAC roles to managed identities
echo "[Step 11/14] Assigning RBAC roles to managed identities..."

# Storage Blob Data Contributor role (backend + celery)
STORAGE_BLOB_CONTRIBUTOR_ROLE="ba92f5b4-2d11-453d-a403-e96b0029c9fe"
STORAGE_ACCOUNT_ID=$(az storage account show --name "${STORAGE_ACCOUNT}" --resource-group "${RESOURCE_GROUP}" --query id -o tsv)

echo "  - Assigning Storage Blob Data Contributor to backend..."
az role assignment create \
  --assignee "${BACKEND_PRINCIPAL_ID}" \
  --role "${STORAGE_BLOB_CONTRIBUTOR_ROLE}" \
  --scope "${STORAGE_ACCOUNT_ID}" \
  --output none 2>/dev/null || echo "    (role already assigned)"

echo "  - Assigning Storage Blob Data Contributor to celery..."
az role assignment create \
  --assignee "${CELERY_PRINCIPAL_ID}" \
  --role "${STORAGE_BLOB_CONTRIBUTOR_ROLE}" \
  --scope "${STORAGE_ACCOUNT_ID}" \
  --output none 2>/dev/null || echo "    (role already assigned)"

# Key Vault Secrets User role (backend + celery)
KEY_VAULT_SECRETS_USER_ROLE="4633458b-17de-408a-b874-0445c86b69e6"
KEY_VAULT_ID=$(az keyvault show --name "${KEY_VAULT_NAME}" --resource-group "${RESOURCE_GROUP}" --query id -o tsv)

echo "  - Assigning Key Vault Secrets User to backend..."
az role assignment create \
  --assignee "${BACKEND_PRINCIPAL_ID}" \
  --role "${KEY_VAULT_SECRETS_USER_ROLE}" \
  --scope "${KEY_VAULT_ID}" \
  --output none 2>/dev/null || echo "    (role already assigned)"

echo "  - Assigning Key Vault Secrets User to celery..."
az role assignment create \
  --assignee "${CELERY_PRINCIPAL_ID}" \
  --role "${KEY_VAULT_SECRETS_USER_ROLE}" \
  --scope "${KEY_VAULT_ID}" \
  --output none 2>/dev/null || echo "    (role already assigned)"

echo "✓ RBAC roles assigned"
echo ""

# Step 12: Set up PostgreSQL MI users and run migrations
echo "[Step 12/17] Setting up PostgreSQL managed identity access..."

# Add temporary firewall rule for client IP
CLIENT_IP=$(curl -s https://ifconfig.me)
echo "  - Adding firewall rule for ${CLIENT_IP}..."
az postgres flexible-server firewall-rule create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${DB_SERVER_NAME}" \
  --rule-name "deploy-client-$(date +%s)" \
  --start-ip-address "${CLIENT_IP}" \
  --end-ip-address "${CLIENT_IP}" \
  --output none

FIREWALL_RULE_NAME=$(az postgres flexible-server firewall-rule list \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${DB_SERVER_NAME}" \
  --query '[-1].name' -o tsv)

# Create MI principals in PostgreSQL
BACKEND_APP_NAME="${ENVIRONMENT_NAME}-backend-api"
CELERY_APP_NAME="${ENVIRONMENT_NAME}-celery-worker"

echo "  - Creating MI principals in PostgreSQL..."
PGPASSWORD="${DB_ADMIN_PASSWORD}" psql \
  "host=${DB_FQDN} dbname=${DB_NAME} user=${DB_ADMIN_LOGIN} sslmode=require" \
  -c "SELECT * FROM pgaadauth_create_principal('${BACKEND_APP_NAME}', false, false);" \
  -c "SELECT * FROM pgaadauth_create_principal('${CELERY_APP_NAME}', false, false);" \
  -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO \"${BACKEND_APP_NAME}\";" \
  -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO \"${CELERY_APP_NAME}\";" \
  -c "GRANT ALL ON SCHEMA public TO \"${BACKEND_APP_NAME}\";" \
  -c "GRANT ALL ON SCHEMA public TO \"${CELERY_APP_NAME}\";" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO \"${BACKEND_APP_NAME}\";" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO \"${CELERY_APP_NAME}\";" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO \"${BACKEND_APP_NAME}\";" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO \"${CELERY_APP_NAME}\";"
echo "✓ MI principals created and permissions granted"

# Run Alembic migrations
echo "  - Running database migrations..."
MIGRATION_DB_URL="postgresql://${DB_ADMIN_LOGIN}:${DB_ADMIN_PASSWORD}@${DB_FQDN}/${DB_NAME}?sslmode=require"
(cd backend && DATABASE_URL="${MIGRATION_DB_URL}" python -m alembic upgrade head)
echo "✓ Migrations complete"

# Remove temporary firewall rule
echo "  - Removing temporary firewall rule..."
az postgres flexible-server firewall-rule delete \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${DB_SERVER_NAME}" \
  --rule-name "${FIREWALL_RULE_NAME}" \
  --yes --output none 2>/dev/null || true
echo "✓ PostgreSQL setup complete"
echo ""

# Step 13: Build and push frontend Docker image with backend URL
echo "[Step 13/17] Building and pushing frontend Docker image..."
az acr build \
  --registry "${ACR_NAME}" \
  --image tracklistify-frontend:latest \
  --file frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_URL="https://${BACKEND_FQDN}" \
  --build-arg NEXT_PUBLIC_WS_URL="wss://${BACKEND_FQDN}" \
  frontend/
echo "✓ Frontend image pushed to ACR"
echo ""

# Step 14: Update frontend container app with new image
echo "[Step 14/17] Updating frontend container app..."
az containerapp update \
  --name "${ENVIRONMENT_NAME}-frontend" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${ACR_NAME}.azurecr.io/tracklistify-frontend:latest" \
  --output none
echo "✓ Frontend container app updated"
echo ""

# Step 15: Restart container apps to pick up MI access
echo "[Step 15/17] Restarting container apps..."
az containerapp revision restart \
  --name "${BACKEND_APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --revision "$(az containerapp revision list --name "${BACKEND_APP_NAME}" -g "${RESOURCE_GROUP}" --query '[0].name' -o tsv)" \
  --output none 2>/dev/null || true
az containerapp revision restart \
  --name "${CELERY_APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --revision "$(az containerapp revision list --name "${CELERY_APP_NAME}" -g "${RESOURCE_GROUP}" --query '[0].name' -o tsv)" \
  --output none 2>/dev/null || true
echo "✓ Container apps restarted"
echo ""

# Step 16: Output deployment summary
echo "[Step 16/17] Waiting for containers to stabilize..."
sleep 30

# Step 17: Deployment summary
echo "[Step 17/17] Deployment complete!"
echo ""
echo "============================================================================"
echo "Deployment Summary"
echo "============================================================================"
echo ""
echo "🌐 Application URLs:"
echo "   Frontend:  https://${FRONTEND_FQDN}"
echo "   Backend:   https://${BACKEND_FQDN}"
echo ""
echo "📦 Resources:"
echo "   Resource Group:    ${RESOURCE_GROUP}"
echo "   ACR:              ${ACR_NAME}.azurecr.io"
echo "   PostgreSQL:       ${DB_FQDN}"
echo "   Redis:            ${REDIS_HOSTNAME}"
echo "   Storage Account:  ${STORAGE_ACCOUNT}"
echo "   Key Vault:        ${KEY_VAULT_NAME}"
echo ""
echo "🔐 Authentication:"
echo "   All services use passwordless authentication via Managed Identity"
echo "   PostgreSQL Entra ID Admin: ${USER_DISPLAY_NAME}"
echo "   Backend Principal ID:      ${BACKEND_PRINCIPAL_ID}"
echo "   Celery Principal ID:       ${CELERY_PRINCIPAL_ID}"
echo ""
echo "✅ Deployment completed successfully!"
echo "============================================================================"
