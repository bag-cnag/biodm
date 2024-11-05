"""Utils."""
import datetime as dt
import json
from functools import reduce, update_wrapper
import operator
from os import path, utime
import re
from typing import (
    Any, List, Callable, Tuple, TypeVar, Dict, Iterator, Self, Generic,
    MutableSet, Iterable, Sequence
)

from starlette.responses import Response


_T = TypeVar("_T")
_U = TypeVar("_U")


# pylint: disable=invalid-name, too-few-public-methods
class aobject:
    """Inheriting this class allows you to define an async __init__.
    Syntax sugar allowing you to create objects like this `await MyClass(params)`.

    Courtesy of: https://stackoverflow.com/a/45364670/6847689

    Quite unpleasant for the linter, but neat to use.
    """
    # pylint: disable=invalid-overridden-method
    async def __new__(cls, *args, **kwargs) -> Self: # type: ignore [misc]
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs) # type: ignore [misc]
        return instance


class classproperty(Generic[_T]):
    """Descriptor combining @classmethod and @property behaviours for python v3.11+.
    notes: only implements the getter and memoizes for subsequent calls.

    Inspired by: https://stackoverflow.com/a/76378416/6847689
    """
    def __init__(self, method: Callable[..., _T]) -> None:
        self.method = method
        self.cache = {}

        update_wrapper(self, method) # type: ignore [misc]

    def __call__(self, cls) -> _T:
        """Not necessary but suppresses Sphinx errors."""
        return self.method(cls)

    def __get__(self, slf, cls=None) -> _T:
        if cls is None:
            cls = type(slf)

        if cls not in self.cache:
            self.cache[cls] = self.method(cls)

        return self.cache[cls]


def utcnow() -> dt.datetime:
    """Support for python==3.10 and below."""
    # pylint: disable=no-member
    try:
        return dt.datetime.now(dt.UTC)
    except ImportError:
        return dt.datetime.utcnow()


def json_response(data: Any, status_code: int) -> Response:
    """Formats a Response object and set application/json header."""
    return Response(
        str(data) + "\n",
        status_code=status_code,
        media_type="application/json"
    )


def json_bytes(d: Dict[Any, Any]) -> bytes:
    """Encodes python Dict as utf-8 bytes."""
    return json.dumps(d).encode('utf-8')


def touch(fname: str) -> None:
    """Python version of the unix shell touch function."""
    if path.exists(fname):
        utime(fname, None)
    else:
        with open(fname, 'a', encoding="utf-8") as f:
            f.close()


# Collections
def to_it(x: _T | Tuple[_T, ...] | List[_T]) -> Tuple[_T, ...] | List[_T]:
    """Return identity list/tuple or pack atomic value in an iterable tuple."""
    return x if isinstance(x, (tuple, list)) else (x,)


def partition(
    ls: Sequence[_T],
    cond: Callable[[_T], bool],
    excl_na: bool = True
) -> Tuple[Sequence[_T], Sequence[_T]]:
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
    # List comprehension with cond(x) or ls.append() makes linters unhappy but runs twice as fast.
    return [
        x for x in ls
        if (
            (excl_na or x) and
            (cond(x) or ls_false.append(x)) # type: ignore [func-returns-value]
        )
    ], ls_false


def unevalled_all(ls: Iterator[Any]) -> Any:
    """Build (ls[0] and ls[1] ... ls[n]) but does not evaluate like all() does."""
    return reduce(operator.and_, ls)


def unevalled_or(ls: Iterator[Any]) -> Any:
    """Build (ls[0] or ls[1] ... ls[n]) but does not evaluate like or() does."""
    return reduce(operator.or_, ls)


def coalesce_dicts(ls: List[Dict[_T, _U]]) -> Dict[_T, _U]:
    """Assembles multiple dicts into one.
    - Overlapping keys: override value in order."""
    return reduce(operator.or_, ls, {})


class OrderedSet(MutableSet[_T]):
    """A set that preserves insertion order by internally using a dict.

    courtesy of: https://stackoverflow.com/a/62019678/6847689
    """
    def __init__(self, iterable: Iterable[_T]):
        self._d = dict.fromkeys(iterable)

    def add(self, x: _T) -> None:
        self._d[x] = None

    def discard(self, x: _T) -> None:
        self._d.pop(x, None)

    def __contains__(self, x: object) -> bool:
        return self._d.__contains__(x)

    def __len__(self) -> int:
        return self._d.__len__()

    def __iter__(self) -> Iterator[_T]:
        return self._d.__iter__()

    def __str__(self):
        return f"{{{', '.join(str(i) for i in self)}}}"

    def __repr__(self):
        return f"<OrderedSet {self}>"


_hash_regexp = re.compile(r'^[0-9a-f]{32}$', re.IGNORECASE)


def check_hash(s: str) -> bool:
    """Check if input string looks like a md5/sha1/sha2 hash.

    i.e. a string of exactly 32 hexadecimal characters

    :param s: string to match
    :type s: str
    :return: string matches flag
    :rtype: bool
    """
    return bool(_hash_regexp.match(s))
