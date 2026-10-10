"""OneBot V11 专有能力：群名查询、合并转发内容获取；其他适配器上降级为不可用"""

from typing import Any

from nonebot import logger
from nonebot.adapters import Bot


def is_onebot(bot: Bot) -> bool:
    return bot.adapter.get_name() == "OneBot V11"


async def fetch_group_name(bot: Bot, group_id: str) -> str | None:
    if not is_onebot(bot):
        return None
    try:
        info = await bot.call_api("get_group_info", group_id=int(group_id))
    except Exception as e:
        logger.debug(f"get_group_info({group_id}) 失败：{e!r}")
        return None
    return (info or {}).get("group_name") or None


async def fetch_forward_nodes(bot: Bot, forward_id: str) -> list[dict[str, Any]]:
    """获取合并转发的节点，统一为 {user_id, nickname, time, message: OneBot 消息段列表}

    兼容 OneBot 标准（`message` 下为 node 消息段）与 NapCat 等实现（`messages` 下为消息事件）
    """
    if not is_onebot(bot):
        raise RuntimeError(f"适配器 {bot.adapter.get_name()} 不支持获取合并转发内容")
    data = await bot.call_api("get_forward_msg", id=forward_id)
    if isinstance(data, list):
        raw = data
    else:
        raw = data.get("messages") or data.get("message") or []
    nodes: list[dict[str, Any]] = []
    for item in raw:
        if item.get("type") == "node":
            d = item.get("data", {})
            nodes.append(
                {
                    "user_id": str(d.get("user_id") or d.get("uin") or ""),
                    "nickname": d.get("nickname") or d.get("name"),
                    "time": d.get("time"),
                    "message": d.get("content") or [],
                }
            )
        else:
            sender = item.get("sender") or {}
            nodes.append(
                {
                    "user_id": str(sender.get("user_id") or item.get("user_id") or ""),
                    "nickname": sender.get("card") or sender.get("nickname"),
                    "time": item.get("time"),
                    "message": item.get("message") or item.get("content") or [],
                }
            )
    return nodes


def to_onebot_message(raw: Any):
    """把 get_forward_msg 返回的消息内容（消息段字典列表或 CQ 码字符串）转为 OneBot V11 Message"""
    from nonebot.adapters.onebot.v11 import Message, MessageSegment

    if isinstance(raw, str):
        return Message(raw)
    return Message(MessageSegment(type=seg["type"], data=seg.get("data") or {}) for seg in raw)
