targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = 'uksouth'

@description('Environment name used for resource naming')
param environmentName string = 'tracklistify'

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('Azure Container Registry name')
param acrName string

@description('Tags to apply to all resources')
param tags object = {}

// Parameters for passwordless authentication
@description('PostgreSQL server host')
param postgresHost string

@description('PostgreSQL database name')
param postgresDatabase string = 'tracklistify'

@description('Redis server host')
param redisHost string

@description('Storage account name for blob storage')
param storageAccountName string

@description('Key Vault URI for secrets')
param keyVaultUri string

@description('CORS allowed origins (comma-separated)')
param corsOrigins string = '*'

@description('Backend API image tag')
param backendImageTag string = 'latest'

@description('Frontend image tag')
param frontendImageTag string = 'latest'

// Azure Container Registry reference
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

// Backend API Container App
resource backendApi 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-backend-api'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend-api'
          image: '${acr.properties.loginServer}/tracklistify-backend:${backendImageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'POSTGRES_HOST'
              value: postgresHost
            }
            {
              name: 'POSTGRES_DB'
              value: postgresDatabase
            }
            {
              name: 'REDIS_HOST'
              value: redisHost
            }
            {
              name: 'STORAGE_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'KEY_VAULT_URI'
              value: keyVaultUri
            }
            {
              name: 'CORS_ORIGINS'
              value: corsOrigins
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Celery Worker Container App (same image as backend, different command)
resource celeryWorker 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-celery-worker'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'celery-worker'
          image: '${acr.properties.loginServer}/tracklistify-backend:${backendImageTag}'
          command: [ 'celery', '-A', 'app.workers.celery_app', 'worker', '--loglevel=info' ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'POSTGRES_HOST'
              value: postgresHost
            }
            {
              name: 'POSTGRES_DB'
              value: postgresDatabase
            }
            {
              name: 'POSTGRES_USER'
              value: '${environmentName}-celery-worker'
            }
            {
              name: 'REDIS_HOST'
              value: redisHost
            }
            {
              name: 'STORAGE_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'KEY_VAULT_URI'
              value: keyVaultUri
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Frontend Container App
resource frontend 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${environmentName}-frontend'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acr.properties.loginServer}/tracklistify-frontend:${frontendImageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'HOSTNAME'
              value: '0.0.0.0'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Assign ACR pull role to the container apps
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource backendAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, backendApi.id, acrPullRoleDefinitionId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: backendApi.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource celeryAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, celeryWorker.id, acrPullRoleDefinitionId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: celeryWorker.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource frontendAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, frontend.id, acrPullRoleDefinitionId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: frontend.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output backendFqdn string = backendApi.properties.configuration.ingress.fqdn
output frontendFqdn string = frontend.properties.configuration.ingress.fqdn
output backendApiName string = backendApi.name
output celeryWorkerName string = celeryWorker.name
output frontendName string = frontend.name
output backendPrincipalId string = backendApi.identity.principalId
output celeryPrincipalId string = celeryWorker.identity.principalId
output frontendPrincipalId string = frontend.identity.principalId
