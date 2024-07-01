from typing import Optional, List, TYPE_CHECKING
from uuid import UUID

from httpx import get
from sqlalchemy import Column, String, Integer, ForeignKey, and_, literal, SQLColumnExpression
from sqlalchemy.sql.functions import func
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, foreign, remote, column_property
from sqlalchemy.ext.hybrid import hybrid_property
from typing import Dict

from biodm.components import Base
from biodm import config
from biodm.exceptions import ImplementionError
from .asso import asso_user_group


if TYPE_CHECKING:
    from .user import User


class Group(Base):
    """Group table."""
    # GroupAlias = aliased("Group")
    # nullable=False is a problem when creating parent entity with just the User.username.
    # id on creation is ensured by read_or_create method from KCService subclasses.
    # KC fields managed internally (not part of the Schema).
    id: Mapped[UUID] = mapped_column(nullable=True)
    #
    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    # test
    n_members: Mapped[int] = mapped_column(nullable=True)

    # relationships
    users: Mapped[List["User"]] = relationship(
        secondary=asso_user_group,
        back_populates="groups",
        # init=False,
    )

    @hybrid_property
    def path_parent(self) -> str:
        return self.path[:self.path.index('__', -1)]

    @path_parent.inplace.expression
    @classmethod
    def _path_parent(cls) -> SQLColumnExpression[String]:
        sep = literal('__')
        if "postgresql" in config.DATABASE_URL:
            return func.substring(
                cls.path,
                0,
                (
                    func.length(cls.path) -
                    func.position(
                        sep.op('IN')(func.reverse(cls.path))
                    )
                )
            )
        elif "sqlite" in config.DATABASE_URL:
            # Attemp #1 from: https://stackoverflow.com/questions/21388820/how-to-get-the-last-index-of-a-substring-in-sqlite
            # Yields: sqlalchemy.exc.StatementError: (builtins.AttributeError) 'str' object has no attribute 'hex'
            # return func.rtrim(cls.path, func.replace(cls.path, sep, ''))
            return func.rtrim(cls.path, func.replace(cls.path, sep, ''))

            # Attempt #2 ?: https://stackoverflow.com/questions/18800589/instr-last-index-of-last-character
            # return func.SUBSTR(cls.path, func.INSTR(cls.path, sep, -1) +1)
            # return func.substr(
            #     cls.path,
            #     0,
            #     func.instr(
            #         cls.path,
            #         sep,
            #         -1
            #     )
            #     - 1
            # )

            #  TODO: support sqlite ?
            #  https://www.sqlitetutorial.net/sqlite-string-functions/

            #  sqlite doesn't have reverse -> have to be declared manually ?
            #  postgres.position -> sqlite.instr
            #  postgres.substring -> sqlite.substr
            #  postgres.length -> sqlite.length
            raise NotImplementedError
        else:
            raise ImplementionError("Only (postgresql | sqlite) backends are suported at the moment.")

    def __repr__(self):
        return f"<Group(path={self.path})>"


# Declare self referencial relationships after table declaration in order to use aliased.
Group_alias = aliased(Group)


Group.parent = relationship(
    Group_alias,
    primaryjoin=Group.path_parent == Group_alias.path,
    foreign_keys=[Group_alias.path],
    uselist=False,
    viewonly=True,
)


Group.children = relationship(
    Group_alias,
    primaryjoin=foreign(Group_alias.path_parent) == Group.path,
    foreign_keys=[Group_alias.path_parent],
    uselist=True,
    viewonly=True,
)
