from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.declarative import declared_attr
import pdb


class Base(DeclarativeBase, AsyncAttrs):
    # def __init__(self, **kw):
    #     """Allow instanciating with nested entities."""
    #     pdb.set_trace()
    #     mapper = self.__dict__.get('__mapper__')
    #     if mapper:
    #         for key in mapper.relationships:
    #             if key in kw:
    #                 kw[key] = mapper.relationships[key].entity.class_(**kw[key])
    #     super().__init__(**kw)

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate tablename."""
        return cls.__name__.upper()
