# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2025 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from asyncpg import Record
from attr import dataclass

from mautrix.types import RoomID
from mautrix.util.async_db import Database

from ..types import TelegramID

fake_db = Database.create("") if TYPE_CHECKING else None

@dataclass
class PortalForumMapping:
    db: ClassVar[Database] = fake_db

    # Portal information
    portal_tgid: TelegramID
    portal_tg_receiver: TelegramID

    # Telegram forum (group thread) ID
    tg_forum_id: int

    # Matrix room
    mxid: RoomID

    # Telegram forum metadata
    title: str | None

    @classmethod
    def _from_row(cls, row: Record | None) -> PortalForumMapping | None:
        if row is None:
            return None
        data = {**row}
        return cls(**data)

    columns: ClassVar[str] = ", ".join(
        (
            "portal_tgid",
            "portal_tg_receiver",
            "tg_forum_id",
            "mxid",
            "title",
        )
    )

    @classmethod
    async def get_for_portal(cls, tgid: TelegramID, tg_receiver: TelegramID) -> list[PortalForumMapping]:
        q = f"""
        SELECT {cls.columns} FROM portal_forum_mapping WHERE portal_tgid=$1 AND portal_tg_receiver=$2
        """
        rows = await cls.db.fetch(q, tgid, tg_receiver)
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_tg_forum_id(cls, tgid: TelegramID, tg_receiver: TelegramID, tg_forum_id: int) -> PortalForumMapping | None:
        q = f"""
        SELECT {cls.columns} FROM portal_forum_mapping WHERE portal_tgid=$1 AND portal_tg_receiver=$2 AND tg_forum_id=$3
        """
        return cls._from_row(await cls.db.fetchrow(q, tgid, tg_receiver, tg_forum_id))

    @classmethod
    async def get_by_mxid(cls, mxid: RoomID) -> PortalForumMapping | None:
        q = f"SELECT {cls.columns} FROM portal_forum_mapping WHERE mxid=$1"
        return cls._from_row(await cls.db.fetchrow(q, mxid))

    @classmethod
    async def all(cls) -> list[PortalForumMapping]:
        rows = await cls.db.fetch(f"SELECT {cls.columns} FROM portal_forum_mapping")
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def update_mxid(cls, old_mxid: RoomID, new_mxid: RoomID):
        await cls.db.execute("UPDATE portal_forum_mapping SET mxid=$1 WHERE mxid=$2", old_mxid, new_mxid)

    @classmethod
    async def update_title(cls, mxid: RoomID, title: str):
        await cls.db.execute("UPDATE portal_forum_mapping SET title=$1 WHERE mxid=$2", title, mxid)

    @property
    def _values(self):
        return (
            self.portal_tgid,
            self.portal_tg_receiver,
            self.tg_forum_id,
            self.mxid,
            self.title
        )

    async def save(self) -> None:
        q = """
        UPDATE portal_forum_mapping SET mxid=$4, title=$5
        WHERE portal_tgid=$1 AND portal_tg_receiver=$2 AND tg_forum_id=$3
        """
        await self.db.execute(q, *self._values)

    async def insert(self) -> None:
        q = """
        INSERT INTO portal_forum_mapping (portal_tgid, portal_tg_receiver, tg_forum_id, mxid, title)
        VALUES ($1, $2, $3, $4, $5)
        """
        await self.db.execute(q, *self._values)

    async def delete(self) -> None:
        q = """
        DELETE FROM portal_forum_mapping
        WHERE portal_tgid=$1 AND $portal_tg_receiver=$2 AND tg_forum_id=$3
        """
        await self.db.execute(q, self.portal_tgid, self.portal_tg_receiver, self.tg_forum_id)
