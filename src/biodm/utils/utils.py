from functools import reduce
import operator
from os import path, utime
from typing import Any, List, Callable, Optional

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

## Collections
def to_it(x: Any) -> (tuple | list):
    """Return identity list/tuple or pack atomic value in a tuple."""
    return x if isinstance(x, (tuple, list)) else (x,)


def it_to(x: tuple | list) -> (Any | tuple | list):
    """Return element for a single element list/tuple else identity list/tuple."""
    return x[0] if hasattr(x, '__len__') and len(x) == 1 else x


def partition(ls: List[Any], cond: Callable[[Any], bool], excl_na: bool=True) -> List[Any]:
    """Partition a list into two based on condition.
    Return list of values checking condition.
    If `excl_na`, values whose truth value is `False` will be evicted from both lists.

    :param ls: input list
    :type ls: list
    :param cond: Condition
    :type cond: Callable[[Any], bool]
    :param excl_na: Exclude empty flag
    :type excl: Optional[bool], True
    :return: Lists of elements separated around condition 
    :rtype: List[Any], List[Any]
    """
    ls_false = []
    return [
        x for x in ls 
        if (excl_na or x) and (cond(x) or ls_false.append(x))
    ], ls_false


def unevalled_all(ls: List[Any]):
    """Build (ls[0] and ls[1] ... ls[n]) but does not evaluate like all() does."""
    return reduce(operator.and_, ls)


def unevalled_or(ls: List[Any]):
    """Build (ls[0] or ls[1] ... ls[n]) but does not evaluate like or() does."""
    return reduce(operator.or_, ls)
