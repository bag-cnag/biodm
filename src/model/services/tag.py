from typing import List

from sqlalchemy import select, delete, update
from sqlalchemy.exc import DatabaseError

from ..dbservice import DatabaseService
from ..tables import Tag


class TagService(DatabaseService):
    async def create(self, data) -> Tag:
        """Receives TagSchema validation result."""
        try:
            return await self._create(data)
        #TODO: Catch dberror everywhere
        except DatabaseError as e:
            self.logger.warning(f"Error creating tag: {e.orig}")
            raise

    async def create_update(self, id, data) -> Tag:
        return await self._merge(id, data)

    async def read(self, id) -> Tag:
        """READ."""
        stmt = select(Tag).where(Tag.id == id)
        return await self._read(stmt)

    async def update(self, id, data) -> Tag:
        """UPDATE."""
        stmt = update(Tag).where(Tag.id == id).values(**data).returning(Tag)
        return await self._update(stmt)

    async def delete(self, id):
        """DELETE."""
        stmt = delete(Tag).where(Tag.id == id)
        return await self._delete(stmt)

    async def find_all(self) -> List[Tag]:
        """Get all rows."""
        stmt = select(Tag)
        return await self._find_all(stmt)
