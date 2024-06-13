"""Utils."""
from collections.abc import MutableMapping
from contextlib import suppress
import datetime as dt
from functools import reduce
import operator
from os import path, utime
from typing import Any, Iterable, List, Callable, MutableSequence, Set, Tuple, TypeVar, Dict

from starlette.responses import Response


_T = TypeVar("_T")
_U = TypeVar("_U")


class aobject(object):
    """Inheriting this class allows you to define an async __init__.
    So you can create objects by doing something like `await MyClass(params)`.

    Courtesy of: https://stackoverflow.com/a/45364670/6847689
    """
    async def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance


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


# def delete_keys_from_dict(d: Dict[_T, _U] | List[Dict[_T, _U]], keys: List[str]) -> Dict[_T, _U]:
#     keys_set = set(keys)
#     modified_dict = {}

#     if isinstance(d, list) and isinstance(d[0], dict):
#         return [delete_keys_from_dict(value, keys_set) for value in d]

#     for key, value in d.items():
#         if key not in keys_set:
#             match value:
#                 case MutableMapping():
#                     modified_dict[key] = delete_keys_from_dict(value, keys_set)
#                 case list():
#                     if isinstance(value[0], dict):
#                         modified_dict[key] = [delete_keys_from_dict(value, keys_set) for value in d]
#                     else:
#                         modified_dict[key] = value    
#                 case _:
#                     modified_dict[key] = value
#     return modified_dict



def delete_keys_from_dict(
    d: Dict[str, _T] | MutableSequence[Dict[str, _T]],
    keys: Iterable[str]
):
    """Inspired from: https://stackoverflow.com/a/49723101/6847689."""
    def delete_keys_from_list_dict(ls: List[Dict[str, _T]], keys_set: Set[str]):
        if len(ls) > 0 and isinstance(ls[0], dict):
            for one in ls:
                delete_keys_from_dict(one, keys_set)

    keys_set = set(keys)

    if isinstance(d, list):
        delete_keys_from_list_dict(d, keys_set)
    else:
        for key in keys_set:
            with suppress(KeyError):
                del d[key]
        for key, value in d.items():
            if isinstance(value, MutableMapping):
                delete_keys_from_dict(value, keys_set)
            elif isinstance(value, list):
                delete_keys_from_list_dict(value, keys_set)
