from typing import Dict, Self, Tuple, Any, TypeVar
from dataclasses import dataclass
from sqlalchemy.sql import Insert


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
    nested: Dict[str, Insert | Self | Tuple[Insert | Self]] # InsertStmt, List[InsertStmt]
    delayed: Dict[str, Insert | Self | Tuple[Insert | Self]] # Union[Insert | Self | List[Insert] | List[Self]]


InsertStmt = TypeVar('InsertStmt', CompositeInsert, Insert)
