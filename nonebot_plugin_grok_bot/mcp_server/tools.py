from typing import Any

from mcp.server.mcpserver.utilities.types import Image as MCPImage
from nonebot_plugin_alconna.uniseg import Reply, UniMessage

from ..core.faces import FACES
from ..core.media import download, image_format
from ..core.message import build_message, dump_segments
from ..core.session import get_history as history_of
from ..core.session import known_sessions, resolve_target
from ..webhook import record_outgoing
from .errors import expose_errors
from .segments import OutSegment, to_segment
from .server import mcp


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
