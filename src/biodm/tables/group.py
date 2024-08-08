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
    # GroupAlias = aliased("Group")
    # nullable=False is a problem when creating parent entity with just the User.username.
    # id on creation is ensured by read_or_create method from KCService subclasses.
    # KC fields managed internally (not part of the Schema).
    id: Mapped[str] = mapped_column(nullable=True)
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

    # @hybrid_property # TODO ?
    # def display_name(self) -> str:
    #     return self.path[self.path.index('__', -1):]

    @path_parent.inplace.expression
    @classmethod
    def _path_parent(cls) -> SQLColumnExpression[str]:
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
