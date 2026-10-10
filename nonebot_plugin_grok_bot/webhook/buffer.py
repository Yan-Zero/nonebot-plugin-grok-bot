"""按路由积压会话消息，并在满足触发条件时推送"""

import asyncio
import fnmatch
from collections import deque
from typing import Any, Literal

from nonebot import get_plugin_config

from ..config import Config, Route
from ..core.session import record_history
from .client import post

config = get_plugin_config(Config)

Trigger = Literal["owner", "interval", "size"]


def match_route(session: str) -> Route | None:
    for route in config.grok_bot_routes:
        if any(fnmatch.fnmatchcase(session, pattern) for pattern in route.sessions):
            return route
    return None


class SessionBuffer:
    def __init__(self, session: str, route: Route) -> None:
        self.session = session
        self.route = route
        self.pending: deque[dict[str, Any]] = deque(maxlen=route.max_pending)
        self.timer: asyncio.Task[None] | None = None

    def add(self, message: dict[str, Any], *, trigger: bool) -> None:
        self.pending.append(message)
        if not trigger:
            return
        if self._owner_triggers(message):
            self.flush("owner")
        elif self.route.flush_size and len(self.pending) >= self.route.flush_size:
            self.flush("size")
        elif self.route.flush_interval is not None and self.timer is None:
            self.timer = asyncio.create_task(self._wait(self.route.flush_interval))

    def _owner_triggers(self, message: dict[str, Any]) -> bool:
        if not message["sender"]["is_owner"]:
            return False
        return self.route.owner_trigger == "always" or (self.route.owner_trigger == "to_me" and message["to_me"])

    async def _wait(self, delay: float) -> None:
        await asyncio.sleep(delay)
        self.timer = None
        self.flush("interval")

    def flush(self, trigger: Trigger) -> None:
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if not self.pending:
            return
        payload = {
            "route": self.route.name,
            "trigger": trigger,
            "session": self.session,
            "messages": list(self.pending),
        }
        self.pending.clear()
        _background(post(self.route, payload))


_buffers: dict[str, SessionBuffer] = {}
_tasks: set[asyncio.Task[None]] = set()


def _background(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def get_buffer(session: str) -> SessionBuffer | None:
    if session not in _buffers:
        if not (route := match_route(session)):
            return None
        _buffers[session] = SessionBuffer(session, route)
    return _buffers[session]


def record_outgoing(session: str, message: dict[str, Any]) -> None:
    """bot 自己发出的消息也记入上下文，但不触发推送"""
    record_history(session, message)
    if buffer := get_buffer(session):
        buffer.add(message, trigger=False)


async def flush_all() -> None:
    """退出前清空积压；只处理配置了自动推送的路由，其余积压只是等待 Owner 触发的上下文"""
    for buffer in _buffers.values():
        if buffer.route.flush_interval is not None or buffer.route.flush_size:
            buffer.flush("interval")
    if _tasks:
        await asyncio.wait(_tasks, timeout=config.grok_bot_webhook_timeout)
