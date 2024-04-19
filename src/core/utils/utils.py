from abc import ABCMeta
from functools import reduce
import operator
from os import path, utime
import uuid
from typing import Any, List

from starlette.responses import Response
from sqlalchemy import inspect


def json_response(data: str, status_code: int) -> Response:
    """Formats a Response object."""
    return Response(
        data + "\n",
        status_code=status_code,
        media_type="application/json"
    )


def touch(fname):
    if path.exists(fname):
        utime(fname, None)
    else:
        open(fname, 'a').close()


def to_it(x: Any) -> (tuple | list):
    """Return identity list/tuple or pack atomic value in a tuple."""
    return x if isinstance(x, (tuple, list)) else (x,)


def it_to(x: tuple | list) -> (Any | tuple | list):
    """Return element for a single element list/tuple else identity list/tuple."""
    return x[0] if hasattr(x, '__len__') and len(x) == 1 else x


def unevalled_all(ls: List[Any]):
    """Build (ls[0] and ls[1] ... ls[n]) but does not evaluate like all() does."""
    return reduce(operator.and_, ls)


def unevalled_or(ls: List[Any]):
    """Build (ls[0] or ls[1] ... ls[n]) but does not evaluate like or() does."""
    return reduce(operator.or_, ls)


def nonce():
    return uuid.uuid4().hex


class Singleton(ABCMeta):
    """Singleton pattern as metaclass."""
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    

# Taken from sqlalchemy_utils instead of adding it as a dependency since this is the only function we are using from that module.
# blob: https://github.com/kvesteri/sqlalchemy-utils/blob/02045c4b24b0767617eea4202a4c570842fe9991/sqlalchemy_utils/functions/orm.py#L24
def get_class_by_table(base, table, data=None):
    """
    Return declarative class associated with given table. If no class is found
    this function returns `None`. If multiple classes were found (polymorphic
    cases) additional `data` parameter can be given to hint which class
    to return.

    ::

        class User(Base):
            __tablename__ = 'entity'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String)


        get_class_by_table(Base, User.__table__)  # User class


    This function also supports models using single table inheritance.
    Additional data paratemer should be provided in these case.

    ::

        class Entity(Base):
            __tablename__ = 'entity'
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String)
            type = sa.Column(sa.String)
            __mapper_args__ = {
                'polymorphic_on': type,
                'polymorphic_identity': 'entity'
            }

        class User(Entity):
            __mapper_args__ = {
                'polymorphic_identity': 'user'
            }


        # Entity class
        get_class_by_table(Base, Entity.__table__, {'type': 'entity'})

        # User class
        get_class_by_table(Base, Entity.__table__, {'type': 'user'})


    :param base: Declarative model base
    :param table: SQLAlchemy Table object
    :param data: Data row to determine the class in polymorphic scenarios
    :return: Declarative class or None.
    """
    found_classes = {
        c for c in base.registry._class_registry.values()
        if hasattr(c, '__table__') and c.__table__ is table
    }
    if len(found_classes) > 1:
        if not data:
            raise ValueError(
                "Multiple declarative classes found for table '{}'. "
                "Please provide data parameter for this function to be able "
                "to determine polymorphic scenarios.".format(
                    table.name
                )
            )
        else:
            for cls in found_classes:
                mapper = inspect(cls)
                polymorphic_on = mapper.polymorphic_on.name
                if polymorphic_on in data:
                    if data[polymorphic_on] == mapper.polymorphic_identity:
                        return cls
            raise ValueError(
                "Multiple declarative classes found for table '{}'. Given "
                "data row does not match any polymorphic identity of the "
                "found classes.".format(
                    table.name
                )
            )
    elif found_classes:
        return found_classes.pop()
    return None
