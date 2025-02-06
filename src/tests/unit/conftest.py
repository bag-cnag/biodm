import pytest

from typing import List, Optional
import marshmallow as ma
import sqlalchemy as sa

from sqlalchemy.orm import relationship, Mapped, mapped_column
from starlette.testclient import TestClient

from biodm.api import Api
from biodm.components import Base, Versioned, Schema
from biodm.components.controllers import ResourceController

# SQLAlchemy
asso_a_b = sa.Table(
    "ASSO_A_B",
    Base.metadata,
    sa.Column("id_a",            sa.ForeignKey("A.id"),        primary_key=True),
    sa.Column("id_b",            sa.Integer(),                 primary_key=True),
    sa.Column("version_b",       sa.Integer(),                 primary_key=True),
    sa.ForeignKeyConstraint(
        ['id_b', 'version_b'], ['B.id', 'B.version']
    )
)

asso_c_d = sa.Table(
    "ASSO_C_D",
    Base.metadata,
    sa.Column("c_id",            sa.ForeignKey("C.id"),        primary_key=True),
    sa.Column("d_id",            sa.Integer(),                 primary_key=True),
    sa.Column("d_version",       sa.Integer(),                 primary_key=True),
    sa.ForeignKeyConstraint(
        ['d_id', 'd_version'], ['D.id', 'D.version']
    )
)


class A(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    x = sa.Column(sa.Integer, nullable=True)
    y = sa.Column(sa.Integer, nullable=True)
    id_c: Mapped[Optional[int]] = mapped_column(sa.Integer, sa.ForeignKey("C.id"), nullable=True)

    bs:    Mapped[List["B"]]  = relationship(secondary=asso_a_b, uselist=True, lazy="joined")
    c:     Mapped["C"] = relationship(foreign_keys=[id_c], backref="ca", lazy="joined")


class B(Versioned, Base):
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, nullable=False)


class C(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    data = sa.Column(sa.String, nullable=False)


class D(Versioned, Base):
    id = sa.Column(sa.Integer, primary_key=True)

    info = sa.Column(sa.String, nullable=False)

    cs:    Mapped[List["C"]]  = relationship(secondary=asso_c_d, uselist=True, lazy="joined")


# Schemas
class ASchema(Schema):
    id = ma.fields.Integer()
    x = ma.fields.Integer()
    y = ma.fields.Integer()
    id_c = ma.fields.Integer()

    bs = ma.fields.List(ma.fields.Nested("BSchema"))
    c = ma.fields.Nested("CSchema")


class BSchema(Schema):
    id = ma.fields.Integer()
    version = ma.fields.Integer()

    name = ma.fields.String()


class CSchema(Schema):
    id = ma.fields.Integer()
    data = ma.fields.String()

    ca = ma.fields.Nested("ASchema")


class DSchema(Schema):
    id = ma.fields.Integer()
    version = ma.fields.Integer()

    info = ma.fields.String()

    cs = ma.fields.List(ma.fields.Nested("CSchema"))


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


class DController(ResourceController):
    def __init__(self, app) -> None:
        super().__init__(app=app, entity="D", table=D, schema=DSchema)


app = Api(
    debug=True,
    controllers=[AController, BController, CController, DController],
    test=True
)

@pytest.fixture
def client():
    with TestClient(app=app, backend_options={
        "use_uvloop": True
    }) as c:
        yield c
