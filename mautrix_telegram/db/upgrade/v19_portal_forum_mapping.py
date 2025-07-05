# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2022 Tulir Asokan
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
from mautrix.util.async_db import Connection, Scheme

from . import upgrade_table


@upgrade_table.register(description="Add portal_forum_mapping")
async def upgrade_v19(conn: Connection) -> None:
    await conn.execute(
        f"""CREATE TABLE portal_forum_mapping (
            portal_tgid        BIGINT NOT NULL,
            portal_tg_receiver BIGINT NOT NULL,
            tg_forum_id        BIGINT NOT NULL,
            mxid               TEXT,
            title              TEXT,

            PRIMARY KEY (portal_tgid, portal_tg_receiver, tg_forum_id),
            FOREIGN KEY (portal_tgid, portal_tg_receiver)
                REFERENCES portal(tgid, tg_receiver)
                ON UPDATE CASCADE ON DELETE CASCADE
        )"""
    )
