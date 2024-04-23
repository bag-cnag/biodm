import asyncio
from typing import Any

import marshmallow as ma
from marshmallow.utils import get_value
from sqlalchemy.ext.asyncio import AsyncSession


class Schema(ma.Schema):
    """Overload marshmallow schema class way of getting attributes in order """
    # def get_attribute(self, obj, key, default):
    #         return obj.get(key, default)
    # async def get_attribute(self, obj: typing.Any, attr: str, default: typing.Any, session: AsyncSession):
    #     """Defines how to pull values from an object to serialize.
    #     """
    #     await session.refresh(obj, attribute_names=[attr])
    #     return ma.Schema.get_value(obj, attr, default)
    def get_attribute(self, obj: Any, attr: str, default: Any, session=None):
        """Defines how to pull values from an object to serialize.

        .. versionadded:: 2.0.0

        .. versionchanged:: 3.0.0a1
            Changed position of ``obj`` and ``attr``.
        """
        async def refresh(session, obj, field):
            await session.refresh(obj, attribute_names=[field])

        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(refresh(session=session, obj=self, field=attr), loop=loop)
        return get_value(obj, attr, default)
