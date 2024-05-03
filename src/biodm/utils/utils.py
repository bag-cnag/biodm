from functools import reduce
import operator
from os import path, utime
from typing import Any, List

from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Bundle


def json_response(data: str, status_code: int) -> Response:
    """Formats a Response object."""
    return Response(
        data + "\n",
        status_code=status_code,
        media_type="application/json"
    )


def touch(fname):
    """Python version of the unix shell touch function."""
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


class DictBundle(Bundle):
    """
    https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#sqlalchemy.orm.Bundle.create_row_processor
    """
    # from biodm.components import Base
    # table: Base
    # def __init__(self, table, *args, **kwargs):
    #     self.table = table
    #     super().__init__(*args, **kwargs)

    def create_row_processor(self, query, procs, labels):
        """
        Return dict object for a friendlier marshmallow serialization
        + avoid contextual label incrementation from sqlalchemy so that field names are consistent.
        """
        # new_labels = []
        # for label in labels:
        #     no_ctx = label.split('_')[0]
        #     new_labels.append(no_ctx if no_ctx in self.table.__table__.c else label)

        def proc(row):
            return dict(
                zip(labels, (proc(row) for proc in procs))
            )
        return proc


async def refresh_sqla_items(item, 
                             table, 
                             session: AsyncSession, 
                             reverse_property: str=None, 
                             level: int=0
):
    """Ensures that lazy nested fields are loaded on n levels.

    No cleaner way of doing it with SQLAlchemy
    refer to: https://github.com/sqlalchemy/sqlalchemy/discussions/9731

    Caution: May badly hurt performaces - use only in case of emergency.
    """
    if not item or not level:
        return

    for one in to_it(item):
        for attr_name, rel in table.relationships().items():
            # Avoid circular refreshing.
            if attr_name != reverse_property:
                await session.refresh(one, attribute_names=[attr_name])

            rev = None
            if rel._reverse_property:
                rev = next(iter(rel._reverse_property))
                rev = str(rev).rsplit('.', maxsplit=1)[-1]

            target = one.target_table(attr_name).decl_class
            await refresh_sqla_items(
                await getattr(one.awaitable_attrs, attr_name), 
                target, session, reverse_property=rev, level=level-1
            )
