# nonebot-plugin-grok-bot

把 NoneBot2 接入 [Grok Bot](https://cursor.com/help/grok-bot)：

- **发送**：插件在 NoneBot 自身的 FastAPI 上挂一个 MCP Server（Streamable HTTP），Grok Bot 通过它发消息，支持图文混排、QQ 内置表情、本地表情包（[savepic](https://github.com/Yan-Zero/nonebot-plugin-savepic)）。
- **接收**：收到的消息按会话路由，POST 到对应 Grok Bot Routine 的 Webhook。

## 安装

```bash
uv add nonebot-plugin-grok-bot            # 基础
uv add "nonebot-plugin-grok-bot[savepic]" # 启用本地表情包
```

驱动器需要同时具备 ASGI 和 HTTP 客户端，例如 `DRIVER=~fastapi+~httpx+~aiohttp`。

## 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `GROK_BOT_MCP_PREFIX` | `/grok_bot` | MCP 端点为 `{prefix}/mcp` |
| `GROK_BOT_MCP_TOKEN` | 无 | MCP 端点的 Bearer Token，在 Grok Bot 里存为 `Authorization` secret |
| `GROK_BOT_OWNERS` | `[]` | Owner 的用户 ID |
| `GROK_BOT_ALLOWED_USERS` | `[]` | 除 Owner 外允许私聊的用户 ID |
| `GROK_BOT_ALLOWED_GROUPS` | `[]` | 允许的群号（频道为 `<guild>/<channel>`） |
| `GROK_BOT_ROUTES` | `[]` | 推送路由，见下 |
| `GROK_BOT_WEBHOOK_TIMEOUT` | `10` | 秒 |
| `GROK_BOT_WEBHOOK_RETRIES` | `3` | 5xx / 429 / 网络错误时重试 |
| `GROK_BOT_HISTORY_SIZE` | `100` | 每个会话保留的最近消息数，供 `get_history` 查询 |

Grok Bot 只能访问公网或 Tailscale 网络内的地址，`HOST` 需要绑定到对应网卡（例如 Tailscale IP 或 `0.0.0.0`）。

### 白名单

- 私聊只接受 Owner 和 `GROK_BOT_ALLOWED_USERS`。
- 群聊只接受 `GROK_BOT_ALLOWED_GROUPS`。

白名单外的消息不记录、不推送，MCP 也不能向其发送。

### 路由

会话标识为 `group:<群号>`、`private:<QQ号>`、`channel:<guild>/<channel>`。路由按顺序匹配（fnmatch），首个命中的生效；未命中的会话不推送。

```json
[
  {
    "name": "owner",
    "sessions": ["private:*"],
    "webhook_url": "https://api2.cursor.sh/automations/webhook/<routine-id>",
    "webhook_key": "crsr_xxx",
    "owner_trigger": "always"
  },
  {
    "name": "groups",
    "sessions": ["group:*"],
    "webhook_url": "https://api2.cursor.sh/automations/webhook/<routine-id>",
    "webhook_key": "crsr_xxx",
    "flush_interval": 300,
    "flush_size": 30,
    "max_pending": 100
  }
]
```

推送时机：

- Owner 的消息：按路由的 `owner_trigger` 决定是否立即推送（并带上该会话中尚未推送的消息）。
  - `always`：Owner 任何发言都推送，适合私聊和特殊群。
  - `to_me`（默认）：仅 @bot、回复 bot 或私聊时推送，群里普通发言不推送。
  - `never`：Owner 也不触发。
- 其他人的消息：先积压起来，满 `flush_size` 条，或第一条积压消息之后过了 `flush_interval` 秒时推送；两者都不设置时，只作为上下文等 Owner 触发。
- bot 自己发出的消息：只记入上下文，不触发推送。

### Webhook Payload

```json
{
  "route": "groups",
  "trigger": "owner",
  "session": "group:123456",
  "messages": [
    {
      "session": "group:123456",
      "message_id": "1001",
      "time": "2026-10-10T18:00:00+08:00",
      "sender": {"user_id": "10000", "nickname": "Yan", "is_owner": true, "is_self": false},
      "to_me": false,
      "segments": [
        {"type": "text", "text": "看看这个"},
        {"type": "image", "url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=…&rkey=…", "sticker": false},
        {"type": "emoji", "id": "14", "name": "微笑"}
      ]
    }
  ]
}
```

`trigger` 为 `owner` / `size` / `interval`。图片直接给原始链接，插件不缓存。QQ 图片链接里的 rkey 会过期，通过 MCP `get_image(url)` 查看或在 `send_message` 中转发时，插件会自动调用 `get_rkey` 重新签发（需要 NapCat / LLOneBot 等支持该扩展 API 的实现）。

## MCP 工具

| 工具 | 说明 |
| --- | --- |
| `send_message(session, segments, reply_to?, self_id?)` | 发送消息，消息段类型有 `text` / `image`（`url` / `base64`）/ `emoji` / `sticker` / `at` / `at_all` |
| `get_history(session, limit)` | 会话最近消息，格式同 Webhook |
| `get_image(url, session?)` | 查看图片，QQ 链接自动续签 rkey |
| `list_sessions()` | 收到过消息的会话 |
| `list_emojis()` | QQ 内置表情 ID → 名称 |
| `search_stickers(query, session, limit)` | 搜索本地表情包（需 savepic） |
| `view_sticker(name, session)` | 查看表情包图片（需 savepic） |

## 开发

```bash
uv sync
uv run pytest
uv run python bot.py
```
