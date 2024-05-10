from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport, Client
import json
import pytest

from typing import List
import marshmallow as ma
import sqlalchemy as sa
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import relationship
from starlette.config import Config

from biodm.api import Api
from biodm.components import Base
from biodm.components.controllers import ResourceController

## SQLAlchemy
asso_a_b = sa.Table(
    "ASSO_A_B",
    Base.metadata,
    sa.Column("id_a",            sa.ForeignKey("A.id"),        primary_key=True),
    sa.Column("id_b",            sa.ForeignKey("B.id"),        primary_key=True),
)


class A(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    x = sa.Column(sa.Integer, nullable=True)
    y = sa.Column(sa.Integer, nullable=True)
    id_c = sa.Column(sa.ForeignKey("C.id"))

    bs:    Mapped[List["B"]]  = relationship(secondary=asso_a_b, uselist=True, lazy="select")
    ac:     Mapped["C"] = relationship(foreign_keys=[id_c], backref="ca", lazy="select")

class B(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, nullable=False)

class C(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    data = sa.Column(sa.String, nullable=False)

## Schemas
class ASchema(ma.Schema):
    id = ma.fields.Integer()
    x = ma.fields.Integer()
    y = ma.fields.Integer()
    id_c = ma.fields.Integer()
    
    bs = ma.fields.List(ma.fields.Nested("B"))


class BSchema(ma.Schema):
    id = ma.fields.Integer()
    name = ma.fields.String(required=True)


class CSchema(ma.Schema):
    id = ma.fields.Integer()
    data = ma.fields.String(required=True)


## Api componenents.
class AController(ResourceController):
    def __init__(self, app):
        super().__init__(app=app, entity="A", table=A, schema=ASchema)

class BController(ResourceController):
    def __init__(self, app):
        super().__init__(app=app, entity="B", table=B, schema=BSchema)

class CController(ResourceController):
    def __init__(self, app):
        super().__init__(app=app, entity="C", table=C, schema=CSchema)

## Config
config = Config()
## Server.
config.API_NAME        = "biodm_test"
config.API_VERSION     = "0.1.0"
config.SERVER_SCHEME   ="http://"
config.SERVER_HOST     ="127.0.0.2"
config.SERVER_PORT     = 8000
config.SECRET_KEY      = "r4nD0m_p455"
config.SERVER_TIMEOUT  = 30
config.INDENT          = 2

## Runtime Flags.
config.DEBUG  = True
config.DEV    = True
config.TEST   = True

## DB.
config.DATABASE_URL = "sqlite:///:memory:"
# ## S3 Bucket.
# S3_ENDPOINT_URL        = config('S3_ENDPOINT_URL',        cast=str,  default="http://s3.local/")
# S3_BUCKET_NAME         = config('S3_BUCKET_NAME',         cast=str,  default="3trdevopal")
# S3_URL_EXPIRATION      = config('S3_URL_EXPIRATION',      cast=int,  default=3600)
# S3_PENDING_EXPIRATION  = config('S3_PENDING_EXPIRATION',  cast=int,  default=3600 * 24)

# ## Keycloak.
# """
# - https://keycloak.local:8443/auth/realms/3TR/.well-known/openid-configuration
# - Warning: Mind the '/auth' if your keycloak instance requires it or not
# """
# KC_HOST            = config("KC_HOST",            cast=str,   default="http://keycloak.local:8080")
# KC_REALM           = config("KC_REALM",           cast=str,   default="3TR")
# KC_PUBLIC_KEY      = config("KC_PUBLIC_KEY",      cast=str,   default="MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtiWvIw3L02fmyj78fPRUU0dN+5zu+rB942pIfO6cexy05+SvnBA4uroHc1F424ZJWngRhfgX+wjL06a1T6sd4c9sfZl2gsP1gsweiajNuf9BCWi542yi3addiuQmbfn6tfmmR/Tr+p+TCrirQiZOp/fEAkGOX/m6y8/t7KMkZewc9rMlCyErld8CPnKMn3Gz8CIHUdcKA6Ena1HPvq/z3rWpBoGI7gycJSEIyxYR+wIXYuQ1EcXhJ6XTv2It0XNbU9VCL16b3vO1nY86bj2HrUfEiKvJLXp1uSzmw3XgF1LqO7z+NAtGUmZIZxpRA4nrrZd22IpSDz50g41qdOBh2wIDAQAB")
# KC_ADMIN           = config("KC_ADMIN",           cast=str,   default="admin")
# KC_ADMIN_PASSWORD  = config("KC_ADMIN_PASSWORD",  cast=str,   default="1234")
# KC_CLIENT_ID       = config("KC_CLIENT_ID",          cast=str,   default="submission_client")
# KC_CLIENT_SECRET   = config("KC_CLIENT_SECRET",      cast=str,   default="Yu6lFwNnewcgVCenn5CArGBX0Cq1Fdor")
# KC_JWT_OPTIONS     = config("KC_JWT_OPTIONS",        cast=dict,  default={'verify_exp': False, 'verify_aud':False})

# ## Kubernetes.
# K8_HOST       = config("K8_HOST",       cast=str,  default="https://minikube.local:8443")
# K8_CERT       = config("K8_CERT",       cast=str,  default="/home/ejodry/.minikube/ca.crt")
# K8_TOKEN      = config("K8_TOKEN",      cast=str,  default='eyJhbGciOiJSUzI1NiIsImtpZCI6InFSZGhFa0EtRUFreUNYMW1yeHFnM3hDcE1oVEwwQnpFMkd5UWxXZkpQa2sifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6Im9taWNzZG0tdG9rZW4iLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoib21pY3NkbSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6Ijc3N2I0ZGY5LWEwMWMtNGU1NC04YjUwLTlkOTcyNTQwZGQ0ZSIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0Om9taWNzZG0ifQ.o2xWuWVHaAvkQOVD6t4p-Kft4dOepj0d8f6KlhUMwQoFNl9FoxdyE0XizMSwDPLCPXz19ADW8JwymmGRD4o1xdbh88rIVDHI9qpgzHLS4swZibUR3YeH7J5JZKoUkBU3YRtpeQfdVzRveElCLTQOpYzza6BhoBISnFEsfVIkZ93Dar11C6uqVeCh6gRNTdZorAiEWX7P76uOYdRNnHBT9rYexMumlh2UdT-oFzEiOcbEye_1nj6EWMOMbSx-ZW9VdWBVT8JtEsgZ_6dLfcxuOauWPhZv9d8T5873l5kl3WyGQTjCduxqd9Mv0So2LhnAn6DayglMYSXColOTDJqZTQ')
# K8_NAMESPACE  = config("K8_NAMESPACE",  cast=str,  default="default")

## Server Object
app = Api(
    debug=True, 
    controllers=[AController, BController, CController],
    instance={
        'config': config,
        # 'tables': tables,
        # 'schemas': schemas,
        # 'manifests': manifests
    }
)

@pytest.fixture()
def client_args() -> dict:
    return {"app": app, 'backend_options': {"use_uvloop": True}}

def json_bytes(d):
    return json.dumps(d).encode('utf-8')
