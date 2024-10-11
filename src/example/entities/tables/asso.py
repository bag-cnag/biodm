from sqlalchemy import Column, Table, ForeignKey, ForeignKeyConstraint

from biodm.components.table import Base


## Associative tables for join operations
asso_dataset_tag = Table(
    "ASSO_DATASET_TAG",
    Base.metadata,
    Column("dataset_id",                                       primary_key=True),
    Column("dataset_version",                                  primary_key=True),
    Column("tag_name",          ForeignKey("TAG.name"),        primary_key=True),
    ForeignKeyConstraint(
        ['dataset_id', 'dataset_version'], ['DATASET.id', 'DATASET.version']
    )
)
