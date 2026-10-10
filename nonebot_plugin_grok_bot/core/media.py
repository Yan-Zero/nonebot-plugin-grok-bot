"""图片 / 文件下载与图片格式识别"""

from nonebot import get_driver, get_plugin_config
from nonebot.adapters import Bot
from nonebot.drivers import HTTPClientMixin, Request

from ..config import Config
from .rkey import is_qq_media, with_rkey

config = get_plugin_config(Config)


async def _get(url: str) -> bytes:
    driver = get_driver()
    if not isinstance(driver, HTTPClientMixin):
        raise RuntimeError("下载需要 HTTP 客户端驱动器（如 ~httpx 或 ~aiohttp）")
    resp = await driver.request(Request("GET", url, timeout=config.grok_bot_download_timeout))
    if resp.status_code != 200 or resp.content is None:
        raise RuntimeError(f"下载失败：HTTP {resp.status_code}（{url}）")
    data = resp.content if isinstance(resp.content, bytes) else resp.content.encode()
    if 0 < config.grok_bot_download_max_size < len(data):
        raise RuntimeError(f"文件过大：{len(data)} 字节，超过上限 {config.grok_bot_download_max_size} 字节")
    return data


async def download(url: str, bot: Bot | None = None) -> bytes:
    """由 NoneBot 下载图片 / 文件；QQ 图片链接先换上有效的 rkey，失败时强制重新签发后再试一次"""
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
