from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from nonebot import get_driver, get_plugin_config, logger
from nonebot.adapters import Bot
from nonebot.drivers import HTTPClientMixin, Request
from nonebot_plugin_alconna.uniseg import (
    At,
    AtAll,
    Emoji,
    Image,
    Reply,
    Target,
    Text,
    UniMessage,
)

from .config import Config
from .faces import FACES
from .rkey import is_qq_media, with_rkey

config = get_plugin_config(Config)


def session_key(target: Target) -> str:
    if target.private:
        return f"private:{target.id}"
    if target.channel:
        return f"channel:{target.parent_id}/{target.id}"
    return f"group:{target.id}"


def is_allowed(session: str) -> bool:
    kind, _, id_ = session.partition(":")
    if kind == "private":
        return id_ in config.grok_bot_owners or id_ in config.grok_bot_allowed_users
    return id_ in config.grok_bot_allowed_groups


def savepic_scope(session: str) -> str:
    kind, _, id_ = session.partition(":")
    return f"qq_group:{id_}" if kind == "group" else "globe"


_targets: dict[str, Target] = {}
_history: defaultdict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=config.grok_bot_history_size))


def remember_target(target: Target) -> str:
    key = session_key(target)
    _targets[key] = target
    return key


def resolve_target(session: str, self_id: str | None = None) -> Target:
    kind, _, id_ = session.partition(":")
    if kind not in ("private", "group", "channel"):
        raise ValueError(f"无法解析的会话：{session}，应为 group:<id> / private:<id> / channel:<guild>/<channel>")
    if not is_allowed(session):
        raise PermissionError(f"会话 {session} 不在白名单中")
    if target := _targets.get(session):
        return target
    if kind == "private":
        return Target(id_, private=True, self_id=self_id)
    if kind == "channel":
        parent_id, _, channel_id = id_.partition("/")
        return Target(channel_id, parent_id=parent_id, channel=True, self_id=self_id)
    return Target(id_, self_id=self_id)


def known_sessions() -> list[str]:
    return list(_targets)


def record_history(session: str, message: dict[str, Any]) -> None:
    _history[session].append(message)


def get_history(session: str, limit: int) -> list[dict[str, Any]]:
    return list(_history[session])[-limit:]


async def _get(url: str) -> bytes:
    driver = get_driver()
    if not isinstance(driver, HTTPClientMixin):
        raise RuntimeError("下载图片需要 HTTP 客户端驱动器（如 ~httpx 或 ~aiohttp）")
    resp = await driver.request(Request("GET", url, timeout=config.grok_bot_webhook_timeout))
    if resp.status_code != 200 or resp.content is None:
        raise RuntimeError(f"下载图片失败：HTTP {resp.status_code}")
    return resp.content if isinstance(resp.content, bytes) else resp.content.encode()


async def download(url: str, bot: Bot | None = None) -> bytes:
    """下载图片；QQ 图片链接先换上有效的 rkey，失败时强制重新签发后再试一次"""
    if not is_qq_media(url):
        return await _get(url)
    try:
        return await _get(await with_rkey(url, bot))
    except RuntimeError:
        return await _get(await with_rkey(url, bot, force=True))


def image_format(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"GIF8"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "jpeg"


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
