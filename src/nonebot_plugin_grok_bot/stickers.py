"""本地表情包，基于可选依赖 nonebot-plugin-savepic"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.plugin import get_plugin
from nonebot_plugin_alconna.uniseg import Image

from .errors import expose_errors
from .rkey import with_rkey
from .session import download, image_format, savepic_scope

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def available() -> bool:
    return get_plugin("nonebot_plugin_savepic") is not None


async def _url(name: str, session: str) -> str:
    if not available():
        raise RuntimeError("未加载 nonebot-plugin-savepic，无法使用本地表情包")
    from nonebot_plugin_savepic.core.sql import select_pic

    if not (url := await select_pic(name, savepic_scope(session))):
        raise ValueError(f"表情包 {name} 不存在，请先用 search_stickers 搜索")
    return url


async def load(name: str, session: str, bot: Bot) -> Image:
    url = await _url(name, session)
    if url.startswith("http"):
        return Image(url=await with_rkey(url, bot), sticker=True)
    return Image(path=Path(url), sticker=True)


def register_tools(mcp: "MCPServer") -> None:
    if not available():
        logger.info("未加载 nonebot-plugin-savepic，跳过表情包工具")
        return

    from mcp.server.mcpserver.utilities.types import Image as MCPImage

    try:
        from nonebot_plugin_savepic.core.sql import search_pic
    except ImportError:
        logger.warning("nonebot-plugin-savepic 版本过旧（缺少 search_pic），跳过表情包工具")
        return

    @mcp.tool()
    @expose_errors
    async def search_stickers(query: str, session: str, limit: int = 10) -> list[dict[str, Any]]:
        """搜索本地表情包，先按名称匹配，不足时按语义相似度补充。

        Args:
            query: 关键词，可以是名称片段或想表达的情绪/含义
            session: 要发送到的会话，决定可用的表情包范围（群表情包 + 全局表情包）
            limit: 最多返回多少个
        """
        return [
            {"name": pic.name, "global": "globe" in pic.scope, "similarity": similarity}
            for pic, similarity in await search_pic(query, savepic_scope(session), limit)
        ]

    @mcp.tool()
    @expose_errors
    async def view_sticker(name: str, session: str) -> MCPImage:
        """查看某个本地表情包的图片内容，确认是否合适再发送"""
        url = await _url(name, session)
        data = await download(url) if url.startswith("http") else await anyio.Path(url).read_bytes()
        return MCPImage(data=data, format=image_format(data))
