import json
import pytest
import os
from pathlib import Path
import re

from typing import List
import marshmallow as ma
import sqlalchemy as sa
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import relationship
from starlette.config import Config
from starlette.testclient import TestClient

import biodm
from biodm.api import Api
from biodm.components import Base
from biodm.components.controllers import ResourceController
import biodm.config

from . import config as testconfig

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
    c:     Mapped["C"] = relationship(foreign_keys=[id_c], backref="ca", lazy="select")


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

    bs = ma.fields.List(ma.fields.Nested("BSchema"))
    c = ma.fields.Nested("CSchema")


class BSchema(ma.Schema):
    id = ma.fields.Integer()
    name = ma.fields.String(required=True)


class CSchema(ma.Schema):
    id = ma.fields.Integer()
    data = ma.fields.String(required=True)

    ca = ma.fields.Nested("ASchema")


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



# with open(Path(Path(__file__).parent, '.env')) as f:
#     config.__dict__ = dict(
#         [
#             re.sub('[\s+\"]', '', line).split("=")
#             for line in f.readlines()
#             if not line.startswith('#') and line.strip()
#         ]
#     )

# ## Load config
# @pytest.fixture(scope="session", autouse=True)
# def set_env(monkeypatch):
#     with open(Path(Path(__file__).parent, '.env')) as f:
#         env = dict(
#             [
#                 re.sub('[\s+\"]', '', line).split("=")
#                 for line in f.readlines()
#                 if not line.startswith('#') and line.strip()
#             ]
#         )
#         for k, v in env.items():
#             monkeypatch.setenv(k, v)
#         # os.environ.update(env)


# @pytest.fixture(scope="session", autouse=True)
# def set_config(monkeypatch):
#     monkeypatch.setattr(biodm.config, "config", testconfig.config)


@pytest.fixture()
def client():
    app = Api(
        debug=True,
        controllers=[AController, BController, CController],
        instance={
            # 'tables': tables,
            # 'schemas': schemas,
            # 'manifests': manifests
        },
        test=True
    )
    with TestClient(app=app, backend_options={
        "use_uvloop": True
    }) as c:
        yield c


def json_bytes(d):
    return json.dumps(d).encode('utf-8')
