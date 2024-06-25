import pytest

from typing import List, Optional
import marshmallow as ma
import sqlalchemy as sa

from sqlalchemy.orm import relationship, Mapped, mapped_column
from starlette.testclient import TestClient

from biodm.api import Api
from biodm.components import Base
from biodm.components.controllers import ResourceController

# SQLAlchemy
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
    id_c: Mapped[Optional[int]] = mapped_column(sa.Integer, sa.ForeignKey("C.id"))

    bs:    Mapped[List["B"]]  = relationship(secondary=asso_a_b, uselist=True, lazy="select")
    c:     Mapped["C"] = relationship(foreign_keys=[id_c], backref="ca", lazy="select")


class B(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, nullable=False)


class C(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    data = sa.Column(sa.String, nullable=False)


# Schemas
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


# Api componenents.
class AController(ResourceController):
    def __init__(self, app) -> None:
        super().__init__(app=app, entity="A", table=A, schema=ASchema)


class BController(ResourceController):
    def __init__(self, app) -> None:
        super().__init__(app=app, entity="B", table=B, schema=BSchema)


class CController(ResourceController):
    def __init__(self, app) -> None:
        super().__init__(app=app, entity="C", table=C, schema=CSchema)


app = Api(
    debug=True,
    controllers=[AController, BController, CController],
    instance={},
    test=True
)

@pytest.fixture
def client():
    with TestClient(app=app, backend_options={
        "use_uvloop": True
    }) as c:
        yield c
