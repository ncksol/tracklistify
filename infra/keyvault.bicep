targetScope = 'resourceGroup'

param location string = 'uksouth'
param environmentName string = 'tracklistify'
param tags object = {}

@secure()
param acrcloudAccessKey string
@secure()
param acrcloudAccessSecret string
param acrcloudHost string = 'identify-eu-west-1.acrcloud.com'

var keyVaultName = take('kv-${environmentName}', 24)

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true
  }
}

resource secretAcrAccessKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'acr-access-key'
  properties: {
    value: acrcloudAccessKey
    contentType: 'text/plain'
  }
}

resource secretAcrAccessSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'acr-access-secret'
  properties: {
    value: acrcloudAccessSecret
    contentType: 'text/plain'
  }
}

resource secretAcrHost 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'acr-host'
  properties: {
    value: acrcloudHost
    contentType: 'text/plain'
  }
}

output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultName string = keyVault.name
