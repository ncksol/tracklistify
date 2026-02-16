param location string = 'uksouth'
param environmentName string = 'tracklistify'

var redisName = 'redis-${environmentName}'

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    redisVersion: '6'
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

output hostName string = redis.properties.hostName
output sslPort int = redis.properties.sslPort
output primaryKey string = listKeys(redis.id, redis.apiVersion).primaryKey
