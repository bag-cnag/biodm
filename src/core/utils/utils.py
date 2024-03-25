import operator
from typing import Any, List
from functools import reduce
import uuid


def to_it(x: Any) -> (tuple | list):
    """Return identity list/tuple or pack atomic value in a tuple."""
    return x if isinstance(x, (tuple, list)) else (x,)


def unevalled_all(ls: List[Any]):
    """Build (ls[0] and ls[1] ... ls[n]) but does not evaluate like all() does."""
    return reduce(operator.and_, ls)


def unevalled_or(ls: List[Any]):
    """Build (ls[0] or ls[1] ... ls[n]) but does not evaluate like or() does."""
    return reduce(operator.or_, ls)


def nonce():
    return uuid.uuid4().hex