from sqlalchemy import Column, Table, ForeignKey, ForeignKeyConstraint

from ..table import Base


## Associative tables for join operations
asso_user_group = Table(
    "ASSO_USER_GROUP",
    Base.metadata,
    Column("id_user",    ForeignKey("USER.id"),    primary_key=True),
    Column("name_group", ForeignKey("GROUP.name"), primary_key=True)
)

asso_dataset_tag = Table(
    "ASSO_DATASET_TAG",
    Base.metadata,
    Column("id_dataset",                                       primary_key=True),
    Column("version_dataset",                                  primary_key=True),
    Column("id_tag",            ForeignKey("TAG.id"),          primary_key=True),
    ForeignKeyConstraint(
        ['id_dataset', 'version_dataset'], ['DATASET.id', 'DATASET.version']
    )
)
