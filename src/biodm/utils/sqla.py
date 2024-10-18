from typing import Dict, Self, Tuple, Any, TypeVar
from dataclasses import dataclass
from sqlalchemy.sql import Insert, Update


@dataclass
class CompositeInsert:
    """Class to hold composite entities statements before insertion.

    :param item: Parent item insert statement
    :type item: Insert
    :param nested: Nested items insert statement indexed by attribute name
    :type nested: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]
    :param delayed: Nested list of items insert statements indexed by attribute name
    :type delayed: Dict[str, Insert | CompositeInsert | List[Insert] | List[CompositeInsert]]
    """

    item: Insert
    nested: Dict[str, Insert | Self | Tuple[Insert | Self]]
    delayed: Dict[str, Insert | Self | Tuple[Insert | Self]]


UpsertStmt = TypeVar('UpsertStmt', CompositeInsert, Insert, Update)


def stmt_to_dict(stmt: UpsertStmt) -> Dict[str, Any]:
    """Returns mapped values as dict for a statement.

    Accesses private attribute _value, may change in a future version of sqla.

    :param stmt: statement
    :type stmt: UpsertStmt
    :return: Dict values.
    :rtype: Dict[str, Any]
    """
    # pylint: disable=protected-access
    return {k.name: v.effective_value for k, v in stmt._values.items() if hasattr(k, 'name')}
