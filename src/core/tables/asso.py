from sqlalchemy import Column, Table, ForeignKey

from core.components.table import Base


## Associative tables for join operations
asso_user_group = Table(
    "ASSO_USER_GROUP",
    Base.metadata,
    Column("id_user",    ForeignKey("USER.id"),    primary_key=True),
    Column("name_group", ForeignKey("GROUP.name"), primary_key=True)
)
