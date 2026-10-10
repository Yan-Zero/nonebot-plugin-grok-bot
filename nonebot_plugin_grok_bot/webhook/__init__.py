"""NoneBot -> Grok Bot：监听消息，按路由推送到 Routine Webhook"""

from nonebot import get_driver, get_plugin_config, on_message
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna.uniseg import UniMsg, get_message_id, get_target

from ..config import Config
from ..core.message import build_message, dump_segments
from ..core.onebot import fetch_group_name
from ..core.session import (
    is_allowed,
    record_history,
    remember_target,
    session_key,
    session_name,
    set_session_name,
)
from .buffer import flush_all, get_buffer
from .buffer import record_outgoing as record_outgoing

config = get_plugin_config(Config)


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
    if session_name(session) is None:
        kind, _, id_ = session.partition(":")
        set_session_name(session, await fetch_group_name(bot, id_) if kind == "group" else nickname)
    message = build_message(
        session,
        session_name(session),
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


get_driver().on_shutdown(flush_all)
