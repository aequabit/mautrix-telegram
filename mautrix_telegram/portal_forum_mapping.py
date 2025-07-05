# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2023 Tulir Asokan
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

from mautrix.types import RoomID

from . import portal as po
from .db import PortalForumMapping as DBPortalForumMapping
from .types import TelegramID

class PortalForumMapping(DBPortalForumMapping):
    def __init__(
        self,
        portal_tgid: TelegramID,
        portal_tg_receiver: TelegramID,
        tg_forum_id: int,
        mxid: RoomID,
        title: str | None = None,
    ) -> None:
        super().__init__(
            portal_tgid=portal_tgid,
            tg_forum_id=tg_forum_id,
            portal_tg_receiver=portal_tg_receiver,
            mxid=mxid,
            title=title,
        )

    async def unbridge(self) -> None:
        portal, _ = await po.Portal.get_by_forum_mxid(self.mxid)
        if not portal:
            return

        await po.Portal.cleanup_room(
            portal.main_intent,
            self.mxid,
            "Forum unbridged",
            puppets_only=True
        )

        await self.delete()

        # TODO: Is this sufficient?
