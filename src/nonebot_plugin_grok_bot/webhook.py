import asyncio
import fnmatch
from collections import deque
from typing import Any, Literal

from nonebot import get_driver, get_plugin_config, logger, on_message
from nonebot.adapters import Bot, Event
from nonebot.drivers import HTTPClientMixin, Request
from nonebot_plugin_alconna.uniseg import UniMsg, get_message_id, get_target

from .config import Config, Route
from .session import build_message, dump_segments, is_allowed, record_history, remember_target, session_key

driver = get_driver()
config = get_plugin_config(Config)

if config.grok_bot_routes and not isinstance(driver, HTTPClientMixin):
    raise RuntimeError("推送 Webhook 需要 HTTP 客户端驱动器（如 ~httpx 或 ~aiohttp）")

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


async def post(route: Route, payload: dict[str, Any]) -> None:
    assert isinstance(driver, HTTPClientMixin)
    headers = {"Authorization": f"Bearer {route.webhook_key}"} if route.webhook_key else {}
    for attempt in range(1, config.grok_bot_webhook_retries + 1):
        try:
            resp = await driver.request(
                Request(
                    "POST",
                    route.webhook_url,
                    headers=headers,
                    json=payload,
                    timeout=config.grok_bot_webhook_timeout,
                )
            )
            if 200 <= resp.status_code < 300:
                logger.debug(f"已推送 {len(payload['messages'])} 条消息到路由 {route.name}（{payload['trigger']}）")
                return
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                logger.error(f"推送到路由 {route.name} 被拒绝：HTTP {resp.status_code} {resp.content!r}")
                return
            logger.warning(f"推送到路由 {route.name} 失败（第 {attempt} 次）：HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"推送到路由 {route.name} 失败（第 {attempt} 次）：{e!r}")
        await asyncio.sleep(2**attempt)
    logger.error(f"推送到路由 {route.name} 最终失败，丢弃 {len(payload['messages'])} 条消息")


def record_outgoing(session: str, message: dict[str, Any]) -> None:
    """bot 自己发出的消息也记入上下文，但不触发推送"""
    record_history(session, message)
    if buffer := get_buffer(session):
        buffer.add(message, trigger=False)


async def _allowed(bot: Bot, event: Event) -> bool:
    try:
        return is_allowed(session_key(get_target(event, bot)))
    except Exception:
        return False


listener = on_message(rule=_allowed, priority=1, block=False)


@listener.handle()
async def _(bot: Bot, event: Event, msg: UniMsg) -> None:
    session = remember_target(get_target(event, bot))
    user_id = event.get_user_id()
    sender = getattr(event, "sender", None)
    nickname = getattr(sender, "card", None) or getattr(sender, "nickname", None)
    message = build_message(
        session,
        get_message_id(event, bot),
        user_id,
        nickname,
        dump_segments(msg),
        is_owner=user_id in config.grok_bot_owners,
        to_me=event.is_tome(),
    )
    record_history(session, message)
    if buffer := get_buffer(session):
        buffer.add(message, trigger=True)


@driver.on_shutdown
async def _() -> None:
    # 只有配置了自动推送的路由才在退出前清空积压，否则这些消息只是等待 Owner 触发的上下文
    for buffer in _buffers.values():
        if buffer.route.flush_interval is not None or buffer.route.flush_size:
            buffer.flush("interval")
    if _tasks:
        await asyncio.wait(_tasks, timeout=config.grok_bot_webhook_timeout)
