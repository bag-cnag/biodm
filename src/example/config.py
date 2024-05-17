from starlette.config import Config

from biodm.utils.utils import touch


touch(".env")
config = Config(".env")


## Server.
API_NAME        = config("SERVER_NAME",     cast=str,  default="dwarf_PoC")
API_VERSION     = config("SERVER_VERSION",  cast=str,  default="0.1.0")
SERVER_SCHEME   = config("SERVER_SCHEME",   cast=str,  default="http://")
SERVER_HOST     = config("SERVER_HOST",     cast=str,  default="127.0.0.1")
SERVER_PORT     = config("SERVER_PORT",     cast=int,  default=8000)
SECRET_KEY      = config("SECRET_KEY",      cast=str,  default="r4nD0m_p455")
SERVER_TIMEOUT  = config("SERVER_TIMEOUT",  cast=int,  default=30)
INDENT          = config('INDENT',          cast=int,  default=2) # For JSON Responses.

## Runtime Flags.
DEBUG  = config('DEBUG',  cast=bool,  default=True)
DEV    = config('DEV',    cast=bool,  default=True)

## DB.
PG_USER  = config("PG_USER",  cast=str,  default="postgres")
PG_PASS  = config("PG_PASS",  cast=str,  default="pass")
PG_HOST  = config("PG_HOST",  cast=str,  default="postgres.local:5432")
PG_DB    = config("PG_DB",    cast=str,  default="biodm")
DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}/{PG_DB}"


## S3 Bucket.
S3_ENDPOINT_URL        = config('S3_ENDPOINT_URL',        cast=str,  default="http://s3.local/")
S3_BUCKET_NAME         = config('S3_BUCKET_NAME',         cast=str,  default="3trdevopal")
S3_URL_EXPIRATION      = config('S3_URL_EXPIRATION',      cast=int,  default=3600)
S3_PENDING_EXPIRATION  = config('S3_PENDING_EXPIRATION',  cast=int,  default=3600 * 24)

## Keycloak.
"""
- https://keycloak.local:8443/auth/realms/3TR/.well-known/openid-configuration
- Warning: Mind the '/auth' if your keycloak instance requires it or not
"""
KC_HOST            = config("KC_HOST",            cast=str,   default="http://keycloak.local:8080")
KC_REALM           = config("KC_REALM",           cast=str,   default="3TR")
KC_PUBLIC_KEY      = config("KC_PUBLIC_KEY",      cast=str,   default="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwI0btgaiQ45tD6KMbzXzF/WYOtZ0dqxf+KOlpQL3lTLusZcwen2Cwpe3hL+JSBNemVMN59ktDZzptJ7p4AmYmX20S31o5xd3WlZXn6UKGLtlTUPm2RBxXmgYELqH2Gnr7MvKRxUo4gsB1+CsW7cPlmGHe/MPYqSrkhy9koE4BfJYpZrcYjfCjadO0lPP1ZNNzW/JC8rf6Vp2dyGU7XhblaE7wB4SHCE9Yiy4e1gXChKlgx+qSibLcuVtx31fulHWVGNO/lVowK3H6FG+Yo34VeaE+oZWXgzejf/8XNh1yXldYmgQD3yLTuL3nOnOyRFvZf3bJRVk1wLdEny2vRxbPQIDAQAB")
KC_ADMIN           = config("KC_ADMIN",           cast=str,   default="admin")
KC_ADMIN_PASSWORD  = config("KC_ADMIN_PASSWORD",  cast=str,   default="1234")
KC_CLIENT_ID       = config("KC_CLIENT_ID",       cast=str,   default="submission_client")
KC_CLIENT_SECRET   = config("KC_CLIENT_SECRET",   cast=str,   default="lSFc2Y0xHGNpsTtKfAebGfY9nAffFAGw")
KC_JWT_OPTIONS     = config("KC_JWT_OPTIONS",     cast=dict,  default={'verify_exp': False, 'verify_aud':False})

## Kubernetes.
K8_HOST       = config("K8_HOST",       cast=str,  default="https://minikube.local:8443")
K8_CERT       = config("K8_CERT",       cast=str,  default="/home/ejodry/.minikube/ca.crt")
K8_TOKEN      = config("K8_TOKEN",      cast=str,  default='eyJhbGciOiJSUzI1NiIsImtpZCI6InFSZGhFa0EtRUFreUNYMW1yeHFnM3hDcE1oVEwwQnpFMkd5UWxXZkpQa2sifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6Im9taWNzZG0tdG9rZW4iLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoib21pY3NkbSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6Ijc3N2I0ZGY5LWEwMWMtNGU1NC04YjUwLTlkOTcyNTQwZGQ0ZSIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0Om9taWNzZG0ifQ.o2xWuWVHaAvkQOVD6t4p-Kft4dOepj0d8f6KlhUMwQoFNl9FoxdyE0XizMSwDPLCPXz19ADW8JwymmGRD4o1xdbh88rIVDHI9qpgzHLS4swZibUR3YeH7J5JZKoUkBU3YRtpeQfdVzRveElCLTQOpYzza6BhoBISnFEsfVIkZ93Dar11C6uqVeCh6gRNTdZorAiEWX7P76uOYdRNnHBT9rYexMumlh2UdT-oFzEiOcbEye_1nj6EWMOMbSx-ZW9VdWBVT8JtEsgZ_6dLfcxuOauWPhZv9d8T5873l5kl3WyGQTjCduxqd9Mv0So2LhnAn6DayglMYSXColOTDJqZTQ')
K8_NAMESPACE  = config("K8_NAMESPACE",  cast=str,  default="default")
