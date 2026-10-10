"""UniMessage 与推送给 Grok Bot 的消息格式之间的转换"""

from datetime import datetime
from typing import Any

from nonebot import logger
from nonebot_plugin_alconna.uniseg import At, AtAll, Emoji, Image, Reply, Text, UniMessage

from .faces import FACES


def dump_segments(message: UniMessage) -> list[dict[str, Any]]:
    """把 UniMessage 转成给 Grok Bot 看的精简格式，与 MCP send_message 的入参格式对应"""
    ret: list[dict[str, Any]] = []
    for seg in message:
        if isinstance(seg, Text):
            ret.append({"type": "text", "text": seg.text})
        elif isinstance(seg, At):
            ret.append({"type": "at", "user_id": seg.target})
        elif isinstance(seg, AtAll):
            ret.append({"type": "at_all"})
        elif isinstance(seg, Emoji):
            ret.append({"type": "emoji", "id": seg.id, "name": seg.name or FACES.get(seg.id)})
        elif isinstance(seg, Image):
            ret.append({"type": "image", "url": seg.url, "sticker": seg.sticker})
        elif isinstance(seg, Reply):
            ret.append({"type": "reply", "message_id": seg.id})
        else:
            logger.debug(f"未专门处理的消息段：{seg!r}")
            ret.append({"type": seg.type, "text": str(seg)})
    return ret


def build_message(
    session: str,
    message_id: str | None,
    user_id: str,
    nickname: str | None,
    segments: list[dict[str, Any]],
    *,
    is_owner: bool = False,
    is_self: bool = False,
    to_me: bool = False,
) -> dict[str, Any]:
    return {
        "session": session,
        "message_id": message_id,
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sender": {"user_id": user_id, "nickname": nickname, "is_owner": is_owner, "is_self": is_self},
        "to_me": to_me,
        "segments": segments,
    }
