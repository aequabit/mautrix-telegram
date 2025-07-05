# mautrix-telegram - A Matrix-Telegram puppeting bridge
# Copyright (C) 2021 Tulir Asokan
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

from typing import Awaitable
import asyncio

from telethon.tl.types import ChannelForbidden, ChatForbidden

from mautrix.types import EventID, RoomID
from mautrix.util import background_task

from ... import portal as po
from ... import portal_forum_mapping as pfm
from ...types import TelegramID
from .. import SECTION_PORTAL_MANAGEMENT, CommandEvent, command_handler
from .util import get_initial_state, user_has_power_level, warn_missing_power


@command_handler(
    needs_auth=False,
    needs_puppeting=False,
    help_section=SECTION_PORTAL_MANAGEMENT,
    help_args="[_id_] [_forum_id_]",
    help_text=(
        "Bridge the specified forum to this Matrix room instead of the main one. "
        "Get _forum_id_ by right-clicking a message within a thread and copying the link: https://t.me/c/.../_forum_id_/..."
    ),
)
async def bridge_forum(evt: CommandEvent) -> EventID:
    if len(evt.args) < 2:
        return await evt.reply(
            "**Usage:** `$cmdprefix+sp bridge-forum <Telegram chat ID> <Telegram forum ID>`"
        )

    # The /id bot command provides the prefixed ID, so we assume
    tgid_str = evt.args[0]
    tgid = None
    try:
        if tgid_str.startswith("-100"):
            tgid = TelegramID(int(tgid_str[4:]))
    except ValueError:
        # Invalid integer
        pass
    if not tgid:
        return await evt.reply(
            "That doesn't seem like a prefixed Telegram chat ID.\n\n"
            "If you did not get the ID using the `/id` bot command, please prefix"
            "channel/supergroup IDs with `-100` and non-super group IDs with `-`.\n\n"
        )

    try:
        tg_forum_id = int(evt.args[1])
    except ValueError:
        return await evt.reply("That forum ID seems invalid. Check the help text for the bridge-forum command.");
        pass

    if tg_forum_id == 1:
        return await evt.reply("The General forum (ID 1) cannot be bridged as a forum");

    portal = await po.Portal.get_by_tgid(tgid, peer_type="channel")
    if not portal or not portal.mxid:
        return await evt.reply(f"To bridge a forum, the group itself must already be bridged.")

    if not await user_has_power_level(portal.mxid, evt.az.intent, evt.sender, "bridge"):
        return await evt.reply(
            f"You do not have the permissions to bridge this room (derived from the main bridge room).")

    portal_forum_mapping = await pfm.PortalForumMapping.get_by_tg_forum_id(tgid, tgid, tg_forum_id)
    if portal_forum_mapping:
        if not await user_has_power_level(portal_forum_mapping.mxid, evt.az.intent, evt.sender, "bridge"):
            return await evt.reply(
                f"You do not have the permissions to bridge this room (derived from the main bridge room).")

        has_forum_portal_message = (
            f"That Telegram forum already has a portal at https://matrix.to/#/{portal_forum_mapping.mxid}."
        )
        if not await user_has_power_level(portal_forum_mapping.mxid, evt.az.intent, evt.sender, "unbridge"):
            return await evt.reply(
                f"{has_forum_portal_message}"
                "Additionally, you do not have the permissions to unbridge that room."
            )
        evt.sender.command_status = {
            "next": confirm_bridge,
            "action": "Room bridging",
            "bridge_to_mxid": evt.room_id,
            "tgid": portal.tgid,
            "tg_forum_id": tg_forum_id,
            "force_use_bot": False,
        }
        return await evt.reply(
            f"{has_forum_portal_message} "
            "However, you have the permissions to unbridge that room.\n\n"
            "To delete that portal completely and continue bridging, use "
            "`$cmdprefix+sp delete-and-continue`. To unbridge the portal "
            "without kicking Matrix users, use `$cmdprefix+sp unbridge-and-"
            "continue`. To cancel, use `$cmdprefix+sp cancel`"
        )
    evt.sender.command_status = {
        "next": confirm_bridge,
        "action": "Room bridging",
        "bridge_to_mxid": evt.room_id,
        "tgid": portal.tgid,
        "tg_forum_id": tg_forum_id,
        "force_use_bot": False,
    }
    return await evt.reply(
        "That Telegram forum has no existing mapping. To confirm bridging the "
        "chat to this room, use `$cmdprefix+sp continue`"
    )

async def confirm_bridge(evt: CommandEvent) -> EventID | None:
    status = evt.sender.command_status
    try:
        portal = await po.Portal.get_by_tgid(status["tgid"], peer_type="channel")
        bridge_to_mxid = status["bridge_to_mxid"]
        tg_forum_id = status["tg_forum_id"]
    except KeyError:
        evt.sender.command_status = None
        return await evt.reply(
            "Fatal error: tgid or tg_forum_id missing from command_status. "
            "This shouldn't happen unless you're messing with the command handler code."
        )

    is_logged_in = await evt.sender.is_logged_in() and not status["force_use_bot"]

    if evt.args[0] != "continue":
        return await evt.reply(
            "Please use `$cmdprefix+sp continue` to confirm the bridging or "
            "`$cmdprefix+sp cancel` to cancel."
        )

    evt.sender.command_status = None
    async with portal._room_create_lock:
        await _locked_confirm_bridge(
            evt, portal=portal, room_id=bridge_to_mxid, tg_forum_id=tg_forum_id, is_logged_in=is_logged_in
        )


async def _locked_confirm_bridge(
    evt: CommandEvent, portal: po.Portal, room_id: RoomID, tg_forum_id: int, is_logged_in: bool
) -> EventID | None:
    user = evt.sender if is_logged_in else evt.tgbot
    try:
        entity = await user.client.get_entity(portal.peer)
    except Exception:
        evt.log.exception("Failed to get_entity(%s) for manual bridging.", portal.peer)
        if is_logged_in:
            return await evt.reply(
                "Failed to get info of telegram chat. You are logged in, are you in that chat?"
            )
        else:
            return await evt.reply(
                "Failed to get info of telegram chat. "
                "You're not logged in, is the relay bot in the chat?"
            )
    if isinstance(entity, (ChatForbidden, ChannelForbidden)):
        if is_logged_in:
            return await evt.reply("You don't seem to be in that chat.")
        else:
            return await evt.reply("The bot doesn't seem to be in that chat.")

    (title, _, levels, _) = await get_initial_state(
        evt.az.intent, evt.room_id
    )

    portal_forum_mapping = pfm.PortalForumMapping(
        portal_tgid=portal.tgid,
        portal_tg_receiver=portal.tg_receiver,
        tg_forum_id=tg_forum_id,
        mxid=room_id,
        title=title
    )

    # try:
    await portal_forum_mapping.insert()
    await portal.update_forum_mappings()
    await portal.update_bridge_info()
    # except Exception as x:
    #     evt.log.exception(f"Failed to save forum mapping: {x}")
    #     return await evt.reply(
    #         "Failed to save forum mapping"
    #     )

    background_task.create(portal.update_matrix_room(user, entity, levels=levels))

    # TODO: This needs work
    #(levels) = await get_initial_state(
    #    evt.az.intent, evt.room_id
    #)
    await warn_missing_power(levels, evt)

    return await evt.reply("Bridging complete.")
