from sqlalchemy import Column, Table, ForeignKey, ForeignKeyConstraint

from biodm.components.table import Base


## Associative tables for join operations
asso_dataset_tag = Table(
    "ASSO_DATASET_TAG",
    Base.metadata,
    Column("id_dataset",                                       primary_key=True),
    Column("version_dataset",                                  primary_key=True),
    Column("name_tag",          ForeignKey("TAG.name"),        primary_key=True),
    ForeignKeyConstraint(
        ['id_dataset', 'version_dataset'], ['DATASET.id', 'DATASET.version']
    )
)
