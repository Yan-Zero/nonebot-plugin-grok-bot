"""UniMessage 与推送给 Grok Bot 的消息格式之间的转换"""

from datetime import datetime
from typing import Any

from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import At, AtAll, Emoji, File, Image, Reference, Reply, Text, UniMessage

from .faces import FACES


def dump_segments(message: UniMessage, bot: Bot | None = None) -> list[dict[str, Any]]:
    """把 UniMessage 转成给 Grok Bot 看的精简格式，与 MCP send_message 的入参格式对应

    传入 bot 时会附带被引用消息的内容（仅展开一层）
    """
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
        elif isinstance(seg, File):
            ret.append(_dump_file(seg))
        elif isinstance(seg, Reply):
            ret.append(_dump_reply(seg, bot))
        elif isinstance(seg, Reference):
            # 合并转发只给 id，内容由 Grok Bot 按需通过 MCP get_forward_message 获取
            ret.append({"type": "forward", "id": seg.id})
        else:
            logger.debug(f"未专门处理的消息段：{seg!r}")
            ret.append({"type": seg.type, "text": str(seg)})
    return ret


def _dump_reply(seg: Reply, bot: Bot | None) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "reply", "message_id": seg.id}
    if sender := getattr(seg.origin, "sender", None):
        data["sender"] = {
            "user_id": str(getattr(sender, "user_id", "") or ""),
            "nickname": getattr(sender, "card", None) or getattr(sender, "nickname", None),
        }
    if bot is not None and seg.msg is not None:
        try:
            quoted = seg.msg if isinstance(seg.msg, UniMessage) else UniMessage.of(seg.msg, bot=bot)
        except Exception as e:
            logger.debug(f"解析被引用消息失败：{e!r}")
        else:
            # 不再传 bot：被引用消息中的引用只给 id，避免层层展开
            data["segments"] = dump_segments(quoted)
    return data


def _dump_file(seg: File) -> dict[str, Any]:
    # uniseg 在缺少 url 时会把文件名当作 url 并补上 https://，因此优先读取适配器原始数据
    data: dict[str, Any] = getattr(getattr(seg, "origin", None), "data", None) or {}
    url = data.get("url") if data else seg.url
    return {
        "type": "file",
        "id": data.get("file_id") or seg.id,
        "name": data.get("file_name") or data.get("file") or seg.name,
        "size": data.get("file_size"),
        "url": url if isinstance(url, str) and url.startswith(("http://", "https://")) else None,
    }


def build_message(
    session: str,
    session_name: str | None,
    message_id: str | None,
    user_id: str,
    nickname: str | None,
    segments: list[dict[str, Any]],
    *,
    group_role: str | None = None,
    is_master: bool = False,
    is_self: bool = False,
    to_me: bool = False,
) -> dict[str, Any]:
    return {
        "session": session,
        "session_name": session_name,
        "message_id": message_id,
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sender": {
            "user_id": user_id,
            "nickname": nickname,
            "group_role": group_role,
            "is_master": is_master,
            "is_self": is_self,
        },
        "to_me": to_me,
        "segments": segments,
    }
