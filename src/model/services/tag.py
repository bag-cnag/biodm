from sqlalchemy import select#, delete
from sqlalchemy.exc import DatabaseError

from model.tables import Tag
from model.dbservice import DatabaseService


class TagService(DatabaseService):
    async def create(self, data):
        """Receives TagSchema validation result."""
        try:
            # return await self._create(item=Tag(**data))
            return await self._create(Tag, data)
        except DatabaseError as e:
            self.logger.warning(f"Error creating album: {e.orig}")
            raise

    async def read(self, id):
        stmt = select(Tag).where(Tag.id == id)
        return await self._read(stmt)

    async def read(self, name):
        stmt = select(Tag).where(Tag.name == name)
        return await self._read(stmt)

    async def update(self, **kwargs):
        """UPDATE."""
        raise NotImplementedError

    async def delete(self, **kwargs):
        """DELETE."""
        raise NotImplementedError

    async def find_all(self, **kwargs):
        """Get all rows."""
        raise NotImplementedError


    # async def get_one(self, album_id):
    #     stmt = select(Tag).where(AlbumModel.upc == album_id)
    #     return await self._get_one(stmt)

    # async def get_many(self):
    #     stmt = select(AlbumModel)
    #     return await self._get_many(stmt)

    # async def create(self, data, tracks):
    #     album = AlbumModel(**data)
    #     album_tracks = [
    #         AlbumTrackModel(track=track_id, album=album.upc) for track_id in tracks
    #     ]

    #     try:
    #         await self._insert([album, *album_tracks])
    #     except DatabaseError as e:
    #         self.log.warning(f"Error creating album: {e.orig}")
    #         raise

    # async def track_add(self, album_id, track_id):
    #     try:
    #         await self._insert([AlbumTrackModel(album=album_id, track=track_id)])
    #     except DatabaseError as e:
    #         self.log.warning(f"Error adding track to album: {e}")
    #         raise

    # async def track_remove(self, album_id, track_id):
    #     stmt = delete(AlbumTrackModel).where(
    #         AlbumTrackModel.album == album_id, AlbumTrackModel.track == track_id
    #     )

    #     try:
    #         await self._delete(stmt)
    #     except IneffectiveDelete as e:
    #         self.log.warning(f"Error removing track from album: {e}")