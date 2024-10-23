from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Self, Tuple, Any, TypeVar, Callable
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.sql import Insert, Update, Select, select, update
from sqlalchemy.sql._typing import _DMLTableArgument

from biodm import config

if TYPE_CHECKING:
    from biodm.components.services import DatabaseService


def _backend_specific_insert() -> Callable[[_DMLTableArgument], Insert]:
    """Returns an insert statement builder according to DB backend.

    For now only postgres/sqlite are supported. They are the ones supporting
    on_conflict_do_x types of insert statements.
    MariaDB/InnoDB have similar constructs, in case we want to support more backends
    the to_stmt method from the UpsertStmtValuesHolder class below should be tweaked as well.
    """
    if 'postgresql' in config.DATABASE_URL.lower():
        return postgresql.insert

    if 'sqlite' in config.DATABASE_URL.lower():
        return sqlite.insert

    raise # Should not happen. Here to suppress linters.


insert: Callable[[_DMLTableArgument], Insert] = _backend_specific_insert()


class UpsertStmtValuesHolder(dict):
    """Dict Class that holds values for an upsert statement.
    Such statement exists as a simple dict during parsing, and is patched during insertion.
    Then the actual statement is emitted just before querying the DB with all possible values."""

    def to_stmt(self, svc: 'DatabaseService') -> Insert | Update | Select:
        """Generates an upsert (Insert + .on_conflict_do_x) depending on data population.
            OR an explicit Update statement for partial data with full primary key
            OR an explicit Select statement for full primary key and no data
        the above edge cases do not necessarily always return a value,
        hence we handle them that way to guarantee consistency.

        In case of incomplete data, some upserts will fail, and raise it up to controller
        which has the details about initial validation fail.
        Ultimately, the goal is to offer support for a more flexible and tolerant mode of writing.

        :param svc: service
        :type svc: DatabaseService
        :return: statement
        :rtype: Insert | Update | Select
        """
        pk = svc.table.pk
        missing_data = svc.table.required - self.keys()

        set_ = {
            key: self[key]
            for key in self.keys() - pk
        }

        if missing_data and all(k in self.keys() for k in pk):
            if set_: # Missing data & pk present & values -> UPDATE.
                stmt = (
                    update(svc.table)
                    .values(**set_)
                    .returning(svc.table)
                )
            else: # ... no values -> SELECT.
                stmt = select(svc.table)
            # Full pk is present so we can generate this where cond.
            stmt = stmt.where(svc.gen_cond([self.get(k) for k in pk]))
            return stmt

        # Regular case
        stmt = insert(svc.table)# or _backend_specific_insert(svc.table)
        stmt = stmt.values(**self)

        if not svc.table.is_versioned:
            if set_: # upsert
                stmt = stmt.on_conflict_do_update(index_elements=pk, set_=set_)
            else: # insert with default values
                stmt = stmt.on_conflict_do_nothing(index_elements=pk)
        # Else (implicit): on_conflict_do_error -> catched by Controller.
        stmt = stmt.returning(svc.table)
        return stmt


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

    item: UpsertStmtValuesHolder
    nested: Dict[str, UpsertStmtValuesHolder | Self | Tuple[UpsertStmtValuesHolder | Self]]
    delayed: Dict[str, UpsertStmtValuesHolder | Self | Tuple[UpsertStmtValuesHolder | Self]]


UpsertStmt = TypeVar('UpsertStmt', CompositeInsert, UpsertStmtValuesHolder)


def stmt_to_dict(stmt: Insert | Update) -> Dict[str, Any]:
    """Returns mapped values as dict for a statement.

    Accesses private attribute _value, may change in a future version of sqla.

    :param stmt: statement
    :type stmt: UpsertStmt
    :return: Dict values.
    :rtype: Dict[str, Any]
    """
    # pylint: disable=protected-access
    return {k.name: v.effective_value for k, v in stmt._values.items() if hasattr(k, 'name')}
