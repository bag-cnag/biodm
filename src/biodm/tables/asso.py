from sqlalchemy import Column, Table, ForeignKey, Integer

from biodm.components.table import Base
"""Associative tables for join operations."""

asso_user_group = Table(
    "ASSO_USER_GROUP",
    Base.metadata,
    Column("user_username",    ForeignKey("USER.username"),    primary_key=True),
    Column("group_path", ForeignKey("GROUP.path"), primary_key=True)
)

asso_list_group = Table(
    "ASSO_LIST_GROUP",
    Base.metadata,
    Column("listgroup_id", ForeignKey("LISTGROUP.id"), primary_key=True),
    Column("group_path", ForeignKey("GROUP.path"), primary_key=True)
)
