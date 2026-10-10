"""QQ NT 图片链接带有会过期的 rkey，过期后通过 OneBot 扩展 API `get_rkey` 重新签发"""

import asyncio
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from nonebot import get_bots, logger
from nonebot.adapters import Bot

_rkeys: dict[str, tuple[datetime, str]] = {}
_lock = asyncio.Lock()


def is_qq_media(url: str) -> bool:
    return urlparse(url).hostname == "multimedia.nt.qq.com.cn"


def _kind(url: str) -> str:
    # appid 1406 为私聊图片，1407 为群聊图片
    return "private" if parse_qs(urlparse(url).query).get("appid") == ["1406"] else "group"


def any_onebot_bot() -> Bot | None:
    return next((bot for bot in get_bots().values() if bot.adapter.get_name() == "OneBot V11"), None)


async def _refresh(bot: Bot, force: bool) -> None:
    async with _lock:
        now = datetime.now()
        if not force and all(_rkeys.get(k, (datetime.min, ""))[0] > now for k in ("group", "private")):
            return
        try:
            ret = await bot.call_api("get_rkey")
        except Exception as e:
            logger.warning(f"get_rkey 调用失败：{e!r}")
            return
        if isinstance(ret, dict):
            ret = ret.get("rkeys", [])
        if not isinstance(ret, list):
            logger.warning(f"get_rkey 返回了奇怪的东西：{ret!r}")
            return
        for item in ret:
            expire = datetime.fromtimestamp(int(item.get("created_at", 0))) + timedelta(
                seconds=int(item.get("ttl", 0)) - 300
            )
            _rkeys[item.get("type")] = (expire, item.get("rkey", "").removeprefix("&rkey="))


async def with_rkey(url: str, bot: Bot | None = None, *, force: bool = False) -> str:
    """给 QQ 图片链接换上当前有效的 rkey，非 QQ 链接或无法获取时原样返回"""
    if not is_qq_media(url) or not (bot := bot or any_onebot_bot()):
        return url
    await _refresh(bot, force)
    if not (rkey := _rkeys.get(_kind(url), (None, ""))[1]):
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["rkey"] = [rkey]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
