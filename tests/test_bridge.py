import asyncio
import json
import time
from collections.abc import Iterator
from typing import Any

import pytest
from nonebot import get_adapter
from nonebot.adapters.onebot.v11 import Adapter, Bot, GroupMessageEvent, Message, MessageSegment, PrivateMessageEvent
from nonebot.drivers import Request, Response
from nonebug import App

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def group_event(
    user_id: int, message: Message, message_id: int = 1, *, group_id: int = 123, to_me: bool = False
) -> GroupMessageEvent:
    return GroupMessageEvent(
        time=int(time.time()),
        self_id=1,
        post_type="message",
        sub_type="normal",
        user_id=user_id,
        message_type="group",
        message_id=message_id,
        message=message,
        original_message=message,
        raw_message=str(message),
        font=0,
        sender={"user_id": user_id, "nickname": f"user{user_id}", "card": ""},
        to_me=to_me,
        group_id=group_id,
    )


@pytest.fixture
def requests(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Request]]:
    from nonebot import get_driver

    sent: list[Request] = []

    async def fake_request(setup: Request) -> Response:
        sent.append(setup)
        if setup.method == "GET":
            return Response(200, content=PNG, request=setup)
        return Response(200, content=b"{}", request=setup)

    monkeypatch.setattr(get_driver(), "request", fake_request)
    yield sent

    from nonebot_plugin_grok_bot.core import session
    from nonebot_plugin_grok_bot.webhook import buffer as webhook

    webhook._buffers.clear()
    session._names.clear()


async def drain() -> None:
    from nonebot_plugin_grok_bot.webhook import buffer as webhook

    for _ in range(10):
        await asyncio.sleep(0)
    if webhook._tasks:
        await asyncio.wait(webhook._tasks)


def posts(requests: list[Request]) -> list[dict[str, Any]]:
    return [
        json.loads(r.content) if isinstance(r.content, (str, bytes)) else r.json for r in requests if r.method == "POST"
    ]


async def test_owner_to_me_flushes_with_pending_context(app: App, requests: list[Request]) -> None:
    async with app.test_matcher() as ctx:
        bot = ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        ctx.receive_event(bot, group_event(20000, Message("路人发言"), 1))
        ctx.should_call_api("get_group_info", {"group_id": 123}, {"group_id": 123, "group_name": "测试群"})
        ctx.receive_event(bot, group_event(10000, Message("主人闲聊"), 2))
        ctx.receive_event(bot, group_event(10000, Message("主人") + MessageSegment.face(14), 3, to_me=True))
    await drain()

    [req] = [r for r in requests if r.method == "POST"]
    assert str(req.url) == "http://hook.test/groups"
    assert req.headers["Authorization"] == "Bearer crsr_test"
    [payload] = posts(requests)
    assert payload["trigger"] == "owner"
    assert payload["session"] == "group:123"
    assert payload["session_name"] == "测试群"
    assert [m["message_id"] for m in payload["messages"]] == ["1", "2", "3"]
    assert payload["messages"][2]["segments"] == [
        {"type": "text", "text": "主人"},
        {"type": "emoji", "id": "14", "name": "微笑"},
    ]


async def test_size_flush_keeps_image_url(app: App, requests: list[Request]) -> None:
    async with app.test_matcher() as ctx:
        bot = ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        for i in range(2):
            ctx.receive_event(bot, group_event(20000 + i, Message(f"消息{i}"), 10 + i))
            if i == 0:
                ctx.should_call_api("get_group_info", {"group_id": 123}, {"group_id": 123, "group_name": "测试群"})
        ctx.receive_event(bot, group_event(20009, Message(MessageSegment.image("https://img.test/a.png")), 12))
    await drain()

    [payload] = posts(requests)
    assert payload["trigger"] == "size"
    assert len(payload["messages"]) == 3
    assert payload["messages"][2]["segments"] == [{"type": "image", "url": "https://img.test/a.png", "sticker": False}]
    # 不应在收到时就下载图片
    assert not [r for r in requests if r.method == "GET"]


async def test_get_image_renews_rkey(app: App, requests: list[Request]) -> None:
    from nonebot_plugin_grok_bot.core import rkey
    from nonebot_plugin_grok_bot.mcp_server import mcp

    rkey._rkeys.clear()
    url = "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=abc&rkey=OLD"
    async with app.test_api() as ctx:
        ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        ctx.should_call_api(
            "get_rkey",
            {},
            [
                {"type": "private", "rkey": "&rkey=PRIV", "created_at": int(time.time()), "ttl": 3600},
                {"type": "group", "rkey": "&rkey=GROUP", "created_at": int(time.time()), "ttl": 3600},
            ],
        )
        result = await mcp.call_tool("get_image", {"url": url})

    assert result.content[0].type == "image"
    assert result.content[0].mime_type == "image/png"
    [get] = [r for r in requests if r.method == "GET"]
    assert "rkey=GROUP" in str(get.url)
    assert "fileid=abc" in str(get.url)


async def test_send_message_mixed(app: App, requests: list[Request]) -> None:
    from nonebot_plugin_grok_bot.mcp_server import mcp

    async with app.test_api() as ctx:
        ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        ctx.should_call_api(
            "send_msg",
            {
                "message_type": "group",
                "group_id": 123,
                "message": Message(
                    [
                        MessageSegment.reply(99),
                        MessageSegment.text("看图"),
                        MessageSegment.image("https://img.test/b.png"),
                        MessageSegment.face(179),
                    ]
                ),
            },
            {"message_id": 555},
        )
        result = await mcp.call_tool(
            "send_message",
            {
                "session": "group:123",
                "reply_to": "99",
                "segments": [
                    {"type": "text", "text": "看图"},
                    {"type": "image", "url": "https://img.test/b.png"},
                    {"type": "emoji", "id": "179"},
                ],
            },
        )
    assert not result.is_error, result
    assert result.structured_content == {"message_ids": ["555"]}

    history = await mcp.call_tool("get_history", {"session": "group:123", "limit": 1})
    [last] = history.structured_content["result"]
    assert last["sender"]["is_self"] is True


async def test_whitelist(app: App, requests: list[Request]) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    from nonebot_plugin_grok_bot.mcp_server import mcp

    async with app.test_matcher() as ctx:
        bot = ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        event = group_event(10000, Message("别的群"), 1, group_id=456, to_me=True)
        ctx.receive_event(bot, event)
        ctx.should_not_pass_rule()
        private = PrivateMessageEvent(
            time=int(time.time()),
            self_id=1,
            post_type="message",
            sub_type="friend",
            user_id=30000,
            message_type="private",
            message_id=2,
            message=Message("陌生人私聊"),
            original_message=Message("陌生人私聊"),
            raw_message="陌生人私聊",
            font=0,
            sender={"user_id": 30000, "nickname": "stranger"},
            to_me=True,
        )
        ctx.receive_event(bot, private)
        ctx.should_not_pass_rule()
    await drain()
    assert not posts(requests)

    with pytest.raises(ToolError, match="白名单"):
        await mcp.call_tool("send_message", {"session": "group:456", "segments": [{"type": "text", "text": "x"}]})


async def test_tool_schema(requests: list[Request]) -> None:
    from nonebot_plugin_grok_bot.mcp_server import mcp

    tools = {t.name: t for t in await mcp.list_tools()}
    assert {"send_message", "get_history", "get_image", "list_emojis", "list_sessions"} <= tools.keys()
    schema = json.dumps(tools["send_message"].input_schema)
    assert "discriminator" in schema or "oneOf" in schema


async def test_tool_errors_are_visible(requests: list[Request]) -> None:
    from mcp.server.mcpserver.exceptions import ToolError

    from nonebot_plugin_grok_bot.mcp_server import mcp

    with pytest.raises(ToolError, match="无法解析的会话"):
        await mcp.call_tool("send_message", {"session": "weird:1", "segments": [{"type": "text", "text": "x"}]})


async def test_forward_is_id_only_and_fetched_on_demand(app: App, requests: list[Request]) -> None:
    from nonebot_plugin_grok_bot.mcp_server import mcp

    async with app.test_matcher() as ctx:
        bot = ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        event = group_event(10000, Message(MessageSegment("forward", {"id": "fw1"})), 1, to_me=True)
        ctx.receive_event(bot, event)
        ctx.should_call_api("get_group_info", {"group_id": 123}, {"group_id": 123, "group_name": "测试群"})
    await drain()
    [payload] = posts(requests)
    assert payload["messages"][0]["segments"] == [{"type": "forward", "id": "fw1"}]
    assert payload["messages"][0]["session_name"] == "测试群"

    async with app.test_api() as ctx:
        ctx.create_bot(base=Bot, adapter=get_adapter(Adapter), self_id="1")
        # NapCat 风格：messages 下为消息事件，内容为消息段字典，且含嵌套转发
        ctx.should_call_api(
            "get_forward_msg",
            {"id": "fw1"},
            {
                "messages": [
                    {
                        "sender": {"user_id": 30001, "nickname": "甲", "card": ""},
                        "time": 1760000000,
                        "message": [
                            {"type": "text", "data": {"text": "第一条"}},
                            {"type": "face", "data": {"id": "14"}},
                        ],
                    },
                    {
                        "sender": {"user_id": 30002, "nickname": "乙"},
                        "time": 1760000001,
                        "message": [{"type": "forward", "data": {"id": "fw2"}}],
                    },
                ]
            },
        )
        result = await mcp.call_tool("get_forward_message", {"forward_id": "fw1", "session": "group:123"})

    nodes = result.structured_content["result"]
    assert [n["user_id"] for n in nodes] == ["30001", "30002"]
    assert nodes[0]["segments"] == [
        {"type": "text", "text": "第一条"},
        {"type": "emoji", "id": "14", "name": "微笑"},
    ]
    assert nodes[1]["segments"] == [{"type": "forward", "id": "fw2"}]

    sessions = await mcp.call_tool("list_sessions", {})
    assert {"session": "group:123", "name": "测试群"} in sessions.structured_content["result"]
