import base64
from contextlib import AsyncExitStack
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image as MCPImage
from nonebot import get_app, get_driver, get_plugin_config, logger
from nonebot.adapters import Bot
from nonebot.drivers import ASGIMixin
from nonebot_plugin_alconna.uniseg import At, AtAll, Emoji, Image, Reply, Segment, Text, UniMessage
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from . import stickers
from .config import Config
from .errors import expose_errors
from .faces import FACES
from .rkey import with_rkey
from .session import (
    build_message,
    download,
    dump_segments,
    image_format,
    known_sessions,
    resolve_target,
)
from .session import (
    get_history as history_of,
)
from .webhook import record_outgoing

driver = get_driver()
config = get_plugin_config(Config)

if not isinstance(driver, ASGIMixin):
    raise RuntimeError("nonebot-plugin-grok-bot 需要 ASGI 驱动器（如 ~fastapi）来挂载 MCP Server")

mcp = MCPServer(
    name="nonebot-grok-bot",
    instructions=(
        "通过这些工具向聊天平台发送消息。会话用 `group:<群号>` / `private:<QQ号>` 表示，"
        "与 Webhook 推送中的 `session` 字段一致。消息由多个消息段组成，可图文混排，"
        "可使用 QQ 内置表情（list_emojis）和本地表情包（search_stickers）。"
    ),
)


class TextSegment(BaseModel):
    type: Literal["text"]
    text: str


class ImageSegment(BaseModel):
    type: Literal["image"]
    url: str | None = Field(default=None, description="图片链接，可直接用 Webhook 推送中的链接（会自动续签 rkey）")
    base64: str | None = Field(default=None, description="base64 编码的图片数据")


class EmojiSegment(BaseModel):
    type: Literal["emoji"]
    id: str = Field(description="QQ 内置表情 ID，见 list_emojis")


class StickerSegment(BaseModel):
    type: Literal["sticker"]
    name: str = Field(description="本地表情包名称，见 search_stickers")


class AtSegment(BaseModel):
    type: Literal["at"]
    user_id: str


class AtAllSegment(BaseModel):
    type: Literal["at_all"]


OutSegment = Annotated[
    TextSegment | ImageSegment | EmojiSegment | StickerSegment | AtSegment | AtAllSegment,
    Field(discriminator="type"),
]


async def to_segment(seg: OutSegment, session: str, bot: Bot) -> Segment:
    match seg:
        case TextSegment(text=text):
            return Text(text)
        case EmojiSegment(id=id_):
            return Emoji(id_, FACES.get(id_))
        case AtSegment(user_id=user_id):
            return At("user", user_id)
        case AtAllSegment():
            return AtAll()
        case StickerSegment(name=name):
            return await stickers.load(name, session, bot)
        case ImageSegment(url=str(url)):
            return Image(url=await with_rkey(url, bot))
        case ImageSegment(base64=str(b64)):
            return Image(raw=base64.b64decode(b64))
        case ImageSegment():
            raise ValueError("image 消息段需要 url 或 base64 之一")
    raise ValueError(f"不支持的消息段：{seg!r}")


@mcp.tool()
@expose_errors
async def send_message(
    session: str,
    segments: list[OutSegment],
    reply_to: str | None = None,
    self_id: str | None = None,
) -> dict[str, Any]:
    """向会话发送一条消息，支持文字、图片、QQ 内置表情、本地表情包、@ 混排。

    Args:
        session: 目标会话，如 `group:123456` 或 `private:123456`
        segments: 消息段列表，按顺序拼接
        reply_to: 要回复的消息 ID（来自 Webhook 推送的 message_id）
        self_id: 指定用哪个 bot 账号发送，默认自动选择
    """
    if not segments:
        raise ValueError("segments 不能为空")
    target = resolve_target(session, self_id)
    bot = await target.select()
    message = UniMessage([await to_segment(seg, session, bot) for seg in segments])
    if reply_to:
        message.insert(0, Reply(reply_to))
    receipt = await target.send(message, bot)
    message_ids = [str(r.id) for r in receipt.get_reply() or []]
    record_outgoing(
        session,
        build_message(
            session, message_ids[0] if message_ids else None, bot.self_id, None, dump_segments(message), is_self=True
        ),
    )
    return {"message_ids": message_ids}


@mcp.tool()
@expose_errors
async def list_sessions() -> list[str]:
    """列出自启动以来收到过消息的会话"""
    return known_sessions()


@mcp.tool()
@expose_errors
async def get_history(session: str, limit: int = 20) -> list[dict[str, Any]]:
    """获取会话最近的消息（包括 bot 自己发的），格式与 Webhook 推送一致"""
    return history_of(session, limit)


@mcp.tool()
@expose_errors
async def get_image(url: str, session: str | None = None) -> MCPImage:
    """查看图片内容，例如 Webhook 推送或历史消息中的图片；QQ 图片链接过期会自动续签

    Args:
        url: 图片链接
        session: 图片所在会话，用于选择续签 rkey 的 bot 账号，可省略
    """
    bot = await resolve_target(session).select() if session else None
    data = await download(url, bot)
    return MCPImage(data=data, format=image_format(data))


@mcp.tool()
@expose_errors
async def list_emojis() -> dict[str, str]:
    """列出常用的 QQ 内置表情，返回 ID -> 名称"""
    return FACES


class _BearerAuth:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != self.expected:
            await send({"type": "http.response.start", "status": 401, "headers": []})
            await send({"type": "http.response.body", "body": b"Unauthorized"})
            return
        await self.app(scope, receive, send)


_mcp_app: ASGIApp = mcp.streamable_http_app(host=str(driver.config.host))
if config.grok_bot_mcp_token:
    _mcp_app = _BearerAuth(_mcp_app, config.grok_bot_mcp_token)
get_app().mount(config.grok_bot_mcp_prefix, _mcp_app)

# 挂载的子应用不会触发自身 lifespan，需要手动管理 session manager
_stack = AsyncExitStack()


@driver.on_startup
async def _() -> None:
    stickers.register_tools(mcp)
    await _stack.enter_async_context(mcp.session_manager.run())
    logger.info(f"Grok Bot MCP Server 已挂载于 {config.grok_bot_mcp_prefix}/mcp")


@driver.on_shutdown
async def _() -> None:
    await _stack.aclose()
