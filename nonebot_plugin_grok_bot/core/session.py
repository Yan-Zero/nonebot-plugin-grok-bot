"""会话标识、白名单、Target 解析与最近消息记录"""

from collections import defaultdict, deque
from typing import Any

from nonebot import get_plugin_config
from nonebot_plugin_alconna.uniseg import Target

from ..config import Config

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
_names: dict[str, str] = {}
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


def known_sessions() -> list[dict[str, str | None]]:
    return [{"session": s, "name": _names.get(s)} for s in _targets]


def session_name(session: str) -> str | None:
    return _names.get(session)


def set_session_name(session: str, name: str | None) -> None:
    if name:
        _names[session] = name


def record_history(session: str, message: dict[str, Any]) -> None:
    _history[session].append(message)


def get_history(session: str, limit: int) -> list[dict[str, Any]]:
    return list(_history[session])[-limit:]
