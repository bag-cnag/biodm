from typing import TYPE_CHECKING, Type

from sqlalchemy.orm.relationships import _RelationshipDeclared

if TYPE_CHECKING:
    from biodm.components import Base


def gen_schema(table: Type['Base']):
    """Generate schema skeletton from table definition."""
    for k in table.__table__.columns:
        print(k.name, table.colinfo(k.name)[1])
    print("---")
    for k, v in table.__dict__.items():
        if hasattr(v, 'prop'):
            p = v.prop
            if isinstance(p, _RelationshipDeclared):
                print(k)
