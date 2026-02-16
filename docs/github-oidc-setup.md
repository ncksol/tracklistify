# GitHub Actions OIDC Setup

One-time setup to enable automated deployments from GitHub Actions to Azure.

## Prerequisites
- Azure CLI installed
- Owner/Contributor access to the Azure subscription
- Admin access to the GitHub repository

## Steps

### 1. Create Azure AD App Registration
```bash
az ad app create --display-name "tracklistify-github-actions"
# Note the appId (CLIENT_ID) from output
```

### 2. Create Service Principal  
```bash
az ad sp create --id <CLIENT_ID>
```

### 3. Add Federated Credential for GitHub
```bash
az ad app federated-credential create --id <CLIENT_ID> --parameters '{
  "name": "github-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:ncksol/tracklistify:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

### 4. Assign Azure Roles
```bash
# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="rg-tracklistify"
ACR_NAME="tracklistifyacr"

# Contributor on resource group
az role assignment create \
  --assignee <CLIENT_ID> \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP

# AcrPush on Container Registry  
az role assignment create \
  --assignee <CLIENT_ID> \
  --role AcrPush \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME
```

### 5. Add GitHub Repository Secrets
Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_TENANT_ID` | Azure tenant ID (`az account show --query tenantId -o tsv`) |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `ACR_LOGIN_SERVER` | e.g., `tracklistifyacr.azurecr.io` |
| `AZURE_RESOURCE_GROUP` | `rg-tracklistify` |

No passwords or keys needed — OIDC handles authentication.

## Verification
Push to main branch and check the CD workflow runs successfully.
