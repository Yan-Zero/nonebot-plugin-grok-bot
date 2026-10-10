"""向 Grok Bot Routine Webhook 发送请求"""

import asyncio
from typing import Any

from nonebot import get_driver, get_plugin_config, logger
from nonebot.drivers import HTTPClientMixin, Request

from ..config import Config, Route

driver = get_driver()
config = get_plugin_config(Config)

if config.grok_bot_routes and not isinstance(driver, HTTPClientMixin):
    raise RuntimeError("推送 Webhook 需要 HTTP 客户端驱动器（如 ~httpx 或 ~aiohttp）")


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
