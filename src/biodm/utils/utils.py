"""Utils."""
import datetime as dt
from functools import reduce
import operator
from os import path, utime
from typing import Any, List, Callable, Tuple, TypeVar, Dict

from starlette.responses import Response


_T = TypeVar("_T")
_U = TypeVar("_U")


def utcnow() -> dt.datetime:
    """Support for python==3.10 and below."""
    # pylint: disable=no-member
    try:
        return dt.datetime.now(dt.UTC)
    except ImportError:
        return dt.datetime.utcnow()


def json_response(data: str, status_code: int) -> Response:
    """Formats a Response object."""
    return Response(
        data + "\n",
        status_code=status_code,
        media_type="application/json"
    )


def touch(fname: str):
    """Python version of the unix shell touch function."""
    if path.exists(fname):
        utime(fname, None)
    else:
        with open(fname, 'a', encoding="utf-8") as f:
            f.close()


# Collections
def to_it(x: _T | Tuple[_T, ...] | List[_T]) -> Tuple[_T, ...] | List[_T]:
    """Return identity list/tuple or pack atomic value in a tuple."""
    return x if isinstance(x, (tuple, list)) else (x,)


def partition(
    ls: List[_T],
    cond: Callable[[_T], bool],
    excl_na: bool = True
) -> Tuple[List[_T], List[_T]]:
    """Partition a list into two based on condition.
    Return list of values checking condition.
    If `excl_na`, values whose truth value is `False` will be evicted from both lists.

    :param ls: input list
    :type ls: list
    :param cond: Condition
    :type cond: Callable[[_T], bool]
    :param excl_na: Exclude empty flag
    :type excl: Optional[bool], True
    :return: Lists of elements separated around condition
    :rtype: List[_T], List[_T]
    """
    ls_false = []
    # List comprehension with cond(x) or ls.append() makes linters unhappy but runs twice faster.
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


def coalesce_dicts(ls: List[Dict[_T, _U]]) -> Dict[_T, _U]:
    """Assembles multiple dicts into one.
    - Overlapping keys: override value in order."""
    return reduce(operator.or_, ls, {})
