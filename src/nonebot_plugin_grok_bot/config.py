from typing import Literal

from pydantic import BaseModel, Field


class Route(BaseModel):
    """一条推送路由：匹配到的会话的消息会推送到对应 Grok Bot 的 Routine Webhook"""

    name: str = "default"
    sessions: list[str] = Field(default_factory=lambda: ["*"])
    """会话匹配规则（fnmatch），如 `group:123`、`private:*`、`*`，按路由顺序首个匹配生效"""
    webhook_url: str
    webhook_key: str | None = None
    """Routine Webhook 的 key，以 `Authorization: Bearer <key>` 发送"""
    owner_trigger: Literal["always", "to_me", "never"] = "to_me"
    """Owner 的消息何时立即推送：always 任何发言；to_me 仅 @bot / 回复 bot / 私聊；never 不触发"""
    flush_interval: float | None = None
    """非 Owner 消息累积多少秒后推送一次，None 表示不按时间推送"""
    flush_size: int | None = None
    """非 Owner 消息累积多少条后推送一次，None 表示不按数量推送"""
    max_pending: int = 100
    """待推送消息的上限，超出后丢弃最旧的；Owner 触发推送时会一并带上"""


class Config(BaseModel):
    # MCP Server（Grok Bot -> NoneBot，用于发送消息）
    grok_bot_mcp_prefix: str = "/grok_bot"
    """MCP 子应用挂载前缀，最终端点为 `{prefix}/mcp`"""
    grok_bot_mcp_token: str | None = None
    """MCP 端点的 Bearer Token，未设置则不鉴权（仅建议本地调试）"""

    # Webhook（NoneBot -> Grok Bot，用于推送收到的消息）
    grok_bot_owners: set[str] = Field(default_factory=set)
    """Owner 的用户 ID，私聊默认只接受 Owner；其消息是否立即推送见 Route.owner_trigger"""
    grok_bot_allowed_users: set[str] = Field(default_factory=set)
    """除 Owner 外，额外允许私聊的用户 ID"""
    grok_bot_allowed_groups: set[str] = Field(default_factory=set)
    """允许的群号（频道为 `<guild>/<channel>`），不在其中的群消息会被忽略，也不能向其发送"""
    grok_bot_routes: list[Route] = Field(default_factory=list)
    grok_bot_webhook_timeout: float = 10.0
    grok_bot_webhook_retries: int = 3

    # 上下文

    grok_bot_history_size: int = 100
    """每个会话保留的最近消息条数，供 MCP `get_history` 查询"""
