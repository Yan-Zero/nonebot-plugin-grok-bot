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
    master_trigger: Literal["always", "to_me", "never"] = "to_me"
    """Master（Bot 主人）的消息何时立即推送：always 任何发言；to_me 仅 @bot / 回复 bot / 私聊；never 不触发"""
    flush_interval: float | None = None
    """非 Master 消息累积多少秒后推送一次，None 表示不按时间推送"""
    flush_size: int | None = None
    """非 Master 消息累积多少条后推送一次，None 表示不按数量推送"""
    max_pending: int = 100
    """待推送消息的上限，超出后丢弃最旧的；Master 触发推送时会一并带上"""


class Config(BaseModel):
    # MCP Server（Grok Bot -> NoneBot，用于发送消息）
    grok_bot_mcp_prefix: str = "/grok_bot"
    """MCP 子应用挂载前缀，最终端点为 `{prefix}/mcp`"""
    grok_bot_mcp_token: str | None = None
    """MCP 端点的 Bearer Token，未设置则不鉴权（仅建议本地调试）"""
    grok_bot_mcp_max_body_size: int = 32 * 1024 * 1024
    """MCP 请求体上限（字节），send_file / send_message 以 base64 传文件和图片时受此限制；mcp 默认仅 4MB"""
    grok_bot_mcp_allowed_hosts: list[str] = Field(default_factory=list)
    """额外允许的 Host 头，如 `mybox.tail1234.ts.net`（支持 `host:*` 匹配任意端口）。
    HOST 为 127.0.0.1 时 mcp 默认只允许 localhost，经 tailscale serve 等反代访问时需要在这里添加"""

    # Webhook（NoneBot -> Grok Bot，用于推送收到的消息）
    grok_bot_masters: set[str] = Field(default_factory=set)
    """Master（Bot 主人，不是群主）的用户 ID；私聊默认只接受 Master，其消息是否立即推送见 Route.master_trigger"""
    grok_bot_allowed_users: set[str] = Field(default_factory=set)
    """除 Master 外，额外允许私聊的用户 ID"""
    grok_bot_allowed_groups: set[str] = Field(default_factory=set)
    """允许的群号（频道为 `<guild>/<channel>`），不在其中的群消息会被忽略，也不能向其发送"""
    grok_bot_routes: list[Route] = Field(default_factory=list)
    grok_bot_webhook_timeout: float = 10.0
    grok_bot_webhook_retries: int = 3

    # 上下文

    # 下载：send_message / send_file 中的 url 由 NoneBot 下载后再交给协议端，
    # 因此只需 NoneBot 能访问（可用 tailnet 等内网地址），不依赖协议端（如容器中的 NapCat）的网络与 DNS
    grok_bot_download_timeout: float = 120.0
    """下载图片 / 文件的超时（秒）"""
    grok_bot_download_max_size: int = 64 * 1024 * 1024
    """下载图片 / 文件的大小上限（字节），防止误传超大文件或异常链接；0 表示不限制"""

    grok_bot_history_size: int = 100
    """每个会话保留的最近消息条数，供 MCP `get_history` 查询"""
