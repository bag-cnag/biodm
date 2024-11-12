from typing import List, TYPE_CHECKING

from sqlalchemy import String, literal, SQLColumnExpression
from sqlalchemy.sql.functions import func
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, foreign
from sqlalchemy.ext.hybrid import hybrid_property

from biodm.components import Base
from biodm import config
from .asso import asso_user_group


if TYPE_CHECKING:
    from .user import User


class Group(Base):
    """Group table."""
    id: Mapped[str] = mapped_column(nullable=not (config.KC_HOST and config.KC_REALM))
    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    # relationships
    users: Mapped[List["User"]] = relationship(
        secondary=asso_user_group,
        back_populates="groups",
        # init=False,
    )

    @hybrid_property
    def parent_path(self) -> str:
        return self.path[:self.path.index('__', -1)]

    # @hybrid_property # TODO ?
    # def display_name(self) -> str:
    #     return self.path[self.path.index('__', -1):]

    @parent_path.inplace.expression
    @classmethod
    def _parent_path(cls) -> SQLColumnExpression[str]:
        sep = literal('__')
        if "postgresql" in str(config.DATABASE_URL):
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
        if "sqlite" in str(config.DATABASE_URL):
            #  sqlite doesn't have reverse
            #            -> strrev declared in dbmanager
            #  postgres.position -> sqlite.instr
            #  postgres.substring -> sqlite.substr
            #  postgres.length -> sqlite.length
            return func.substr(cls.path,
                0,
                (
                    func.length(cls.path) -
                    func.instr(
                        func.strrev(cls.path),
                        sep
                    )
                )
            )
        raise NotImplementedError

    def __repr__(self):
        return f"<Group(path={self.path})>"


# Declare self referencial relationships after table declaration in order to use aliased.
Group_alias = aliased(Group)


Group.parent = relationship(
    Group_alias,
    primaryjoin=Group.parent_path == Group_alias.path,
    foreign_keys=[Group_alias.path],
    uselist=False,
    viewonly=True,
)


Group.children = relationship(
    Group_alias,
    primaryjoin=foreign(Group_alias.parent_path) == Group.path,
    foreign_keys=[Group_alias.parent_path],
    uselist=True,
    viewonly=True,
)
