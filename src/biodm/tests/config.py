from starlette.config import Config

config = Config()

## Server.
config.API_NAME        = "biodm_test"
config.API_VERSION     = "0.1.0"
config.SERVER_SCHEME   = "http://"
config.SERVER_HOST     = "127.0.0.2"
config.SERVER_PORT     = 8000
config.SECRET_KEY      = "r4nD0m_p455"
config.SERVER_TIMEOUT  = 30
config.INDENT          = 2

# ## Runtime Flags.
# config.DEBUG  = True
# config.DEV    = True
# config.TEST   = True

## DB.
config.DATABASE_URL = "sqlite:///:memory:"
## S3 Bucket.
# config.S3_ENDPOINT_URL        = default="http://s3.local/"
# config.S3_BUCKET_NAME         = "3trdevopal"
# config.S3_URL_EXPIRATION      = 3600
# config.S3_PENDING_EXPIRATION  = 3600 * 24

## Keycloak.
# config.KC_HOST            = "http://keycloak.local:8080"
# config.KC_REALM           = "3TR"
# config.KC_PUBLIC_KEY      = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtiWvIw3L02fmyj78fPRUU0dN+5zu+rB942pIfO6cexy05+SvnBA4uroHc1F424ZJWngRhfgX+wjL06a1T6sd4c9sfZl2gsP1gsweiajNuf9BCWi542yi3addiuQmbfn6tfmmR/Tr+p+TCrirQiZOp/fEAkGOX/m6y8/t7KMkZewc9rMlCyErld8CPnKMn3Gz8CIHUdcKA6Ena1HPvq/z3rWpBoGI7gycJSEIyxYR+wIXYuQ1EcXhJ6XTv2It0XNbU9VCL16b3vO1nY86bj2HrUfEiKvJLXp1uSzmw3XgF1LqO7z+NAtGUmZIZxpRA4nrrZd22IpSDz50g41qdOBh2wIDAQAB"
# config.KC_ADMIN           = "admin"
# config.KC_ADMIN_PASSWORD  = "1234"
# config.KC_CLIENT_ID       = "submission_client"
# config.KC_CLIENT_SECRET   = "Yu6lFwNnewcgVCenn5CArGBX0Cq1Fdor"
# config.KC_JWT_OPTIONS     = {'verify_exp': False, 'verify_aud':False}

## Kubernetes.
# config.K8_HOST       = "https://minikube.local:8443"
# config.K8_CERT       = "/home/ejodry/.minikube/ca.crt"
# config.K8_TOKEN      = 'eyJhbGciOiJSUzI1NiIsImtpZCI6InFSZGhFa0EtRUFreUNYMW1yeHFnM3hDcE1oVEwwQnpFMkd5UWxXZkpQa2sifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6Im9taWNzZG0tdG9rZW4iLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoib21pY3NkbSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6Ijc3N2I0ZGY5LWEwMWMtNGU1NC04YjUwLTlkOTcyNTQwZGQ0ZSIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0Om9taWNzZG0ifQ.o2xWuWVHaAvkQOVD6t4p-Kft4dOepj0d8f6KlhUMwQoFNl9FoxdyE0XizMSwDPLCPXz19ADW8JwymmGRD4o1xdbh88rIVDHI9qpgzHLS4swZibUR3YeH7J5JZKoUkBU3YRtpeQfdVzRveElCLTQOpYzza6BhoBISnFEsfVIkZ93Dar11C6uqVeCh6gRNTdZorAiEWX7P76uOYdRNnHBT9rYexMumlh2UdT-oFzEiOcbEye_1nj6EWMOMbSx-ZW9VdWBVT8JtEsgZ_6dLfcxuOauWPhZv9d8T5873l5kl3WyGQTjCduxqd9Mv0So2LhnAn6DayglMYSXColOTDJqZTQ'
# config.K8_NAMESPACE  = "default"