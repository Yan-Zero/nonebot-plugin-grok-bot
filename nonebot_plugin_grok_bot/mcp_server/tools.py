import base64 as b64
import binascii
from typing import Any

from mcp.server.mcpserver.utilities.types import Image as MCPImage
from nonebot_plugin_alconna.uniseg import File, Reply, UniMessage

from ..core.faces import FACES
from ..core.media import download, image_format
from ..core.message import build_message, dump_segments
from ..core.onebot import fetch_file_url, fetch_forward_nodes, is_onebot, to_onebot_message, upload_file
from ..core.session import get_history as history_of
from ..core.session import known_sessions, resolve_target, session_name
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
            session,
            session_name(session),
            message_ids[0] if message_ids else None,
            bot.self_id,
            None,
            dump_segments(message),
            is_self=True,
        ),
    )
    return {"message_ids": message_ids}


@mcp.tool()
@expose_errors
async def send_file(
    session: str,
    name: str,
    url: str | None = None,
    base64: str | None = None,
    self_id: str | None = None,
) -> dict[str, Any]:
    """向会话发送文件（群聊为上传群文件，私聊为发送文件）。文件不能与普通消息混发，需单独调用。

    Args:
        session: 目标会话，如 `group:123456` 或 `private:123456`
        name: 文件名（含扩展名），如 `report.pdf`
        url: 文件下载链接，与 base64 二选一；由网关（NoneBot）下载，可使用 tailnet 等网关可访问的内网地址
        base64: base64 编码的文件内容（可带 `data:...;base64,` 前缀），与 url 二选一；受请求体大小限制
        self_id: 指定用哪个 bot 账号发送，默认自动选择
    """
    if not name.strip():
        raise ValueError("name 不能为空")
    if (url is None) == (base64 is None):
        raise ValueError("url 与 base64 需且仅需提供一个")
    raw: bytes | None = None
    if base64 is not None:
        base64 = base64.split(",", 1)[1] if base64.startswith("data:") else base64
        try:
            raw = b64.b64decode(base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"base64 内容无效：{e}") from e

    target = resolve_target(session, self_id)
    bot = await target.select()
    if raw is None:
        # 由 NoneBot 下载，协议端无需能访问该 url（可用 tailnet 等内网地址）
        raw = await download(url, bot)
    if is_onebot(bot):
        await upload_file(
            bot,
            private=target.private,
            target_id=target.id,
            file="base64://" + b64.b64encode(raw).decode(),
            name=name,
        )
    else:
        await target.send(UniMessage(File(raw=raw, name=name)), bot)

    record_outgoing(
        session,
        build_message(
            session,
            session_name(session),
            None,
            bot.self_id,
            None,
            [{"type": "file", "name": name, "size": len(raw)}],
            is_self=True,
        ),
    )
    return {"ok": True, "name": name, "size": len(raw)}


@mcp.tool()
@expose_errors
async def list_sessions() -> list[dict[str, str | None]]:
    """列出自启动以来收到过消息的会话及其名称（群名 / 私聊对象昵称）"""
    return known_sessions()


@mcp.tool()
@expose_errors
async def get_file(file_id: str, session: str) -> dict[str, Any]:
    """用收到的文件消息段（`{"type": "file", "id": ...}`）的 id 换取下载链接。
    若为图片文件，可再用 get_image(url) 直接查看。

    Args:
        file_id: 文件消息段的 id
        session: 该文件所在的会话
    """
    target = resolve_target(session)
    bot = await target.select()
    info = await fetch_file_url(bot, private=target.private, target_id=target.id, file_id=file_id)
    name = (info.get("name") or "").lower()
    if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
        info["hint"] = "这是图片文件，可用 get_image(url) 直接查看"
    return info


@mcp.tool()
@expose_errors
async def get_forward_message(forward_id: str, session: str) -> list[dict[str, Any]]:
    """获取合并转发（聊天记录）的内容。消息中 `{"type": "forward", "id": ...}` 消息段的 id 即为 forward_id；
    返回的节点内若还有 forward 消息段，可继续用其 id 查询。

    Args:
        forward_id: 合并转发的 id
        session: 该转发所在的会话，用于选择 bot 账号
    """
    bot = await resolve_target(session).select()
    return [
        {
            "user_id": node["user_id"],
            "nickname": node["nickname"],
            "time": node["time"],
            "segments": dump_segments(UniMessage.of(to_onebot_message(node["message"]), bot=bot), bot),
        }
        for node in await fetch_forward_nodes(bot, forward_id)
    ]


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
