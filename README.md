<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-grok-bot

_✨ 通过 MCP Server 与 Webhook 将聊天接入 Grok Bot ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/Yan-Zero/nonebot-plugin-grok-bot.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-grok-bot">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-grok-bot.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="python">

</div>

## 📖 介绍

把 NoneBot2 接入 [Grok Bot](https://cursor.com/help/grok-bot)：

- **发送**：插件在 NoneBot 自身的 FastAPI 上挂载一个 MCP Server（Streamable HTTP），Grok Bot 通过它发送消息，支持图文混排、QQ 内置表情和本地表情包（基于 [savepic](https://github.com/Yan-Zero/nonebot-plugin-savepic)）。
- **接收**：收到的消息按会话路由，POST 到对应 Grok Bot Routine 的 Webhook。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-grok-bot

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>uv</summary>

    uv add nonebot-plugin-grok-bot
</details>
<details>
<summary>pip</summary>

    pip install nonebot-plugin-grok-bot
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-grok-bot
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-grok-bot
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_grok_bot"]

</details>

如需使用本地表情包，请安装 `savepic` 可选依赖（例如 `pip install "nonebot-plugin-grok-bot[savepic]"`），并按 savepic 的说明完成配置。

## ⚙️ 配置

驱动器需要同时具备 ASGI 和 HTTP 客户端，例如：

    DRIVER=~fastapi+~httpx+~aiohttp

### 通过 Tailscale 暴露 MCP 端点

NoneBot 保持监听 `127.0.0.1`，由 Tailscale 只转发 MCP 路径（不要把整个端口暴露出去，否则 OneBot 的连接端点也会一起暴露）：

    # 仅 tailnet 内可访问（Grok Bot 所在机器需加入同一 tailnet）
    tailscale serve --bg --set-path /grok_bot http://127.0.0.1:8080/grok_bot

    # 或：公网可访问（需在 tailnet ACL 中为该节点开启 funnel）
    tailscale funnel --bg --set-path /grok_bot http://127.0.0.1:8080/grok_bot

    # 查看 / 撤销
    tailscale serve status
    tailscale serve reset

需要在 Tailscale 管理后台开启 MagicDNS 与 HTTPS 证书。之后在 `.env.prod` 中把域名加入 `GROK_BOT_MCP_ALLOWED_HOSTS`，并在 Grok Bot 中添加 MCP 连接器：

- URL：`https://mybox.tail1234.ts.net/grok_bot/mcp`
- Secret：`Authorization: Bearer <GROK_BOT_MCP_TOKEN>`

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| GROK_BOT_MCP_PREFIX | 否 | `/grok_bot` | MCP 端点为 `{prefix}/mcp` |
| GROK_BOT_MCP_TOKEN | 否 | 无 | MCP 端点的 Bearer Token，在 Grok Bot 中存为 `Authorization` secret；不设置则不鉴权 |
| GROK_BOT_MCP_ALLOWED_HOSTS | 否 | `[]` | 额外允许的 Host 头，经 `tailscale serve` 等反代访问时填写域名，如 `["mybox.tail1234.ts.net"]` |
| GROK_BOT_OWNERS | 是 | `[]` | Owner 的用户 ID |
| GROK_BOT_ALLOWED_USERS | 否 | `[]` | 除 Owner 外允许私聊的用户 ID |
| GROK_BOT_ALLOWED_GROUPS | 否 | `[]` | 允许的群号（频道为 `<guild>/<channel>`） |
| GROK_BOT_ROUTES | 是 | `[]` | 推送路由，见下文 |
| GROK_BOT_WEBHOOK_TIMEOUT | 否 | `10` | Webhook 请求超时（秒） |
| GROK_BOT_WEBHOOK_RETRIES | 否 | `3` | 5xx / 429 / 网络错误时的重试次数 |
| GROK_BOT_HISTORY_SIZE | 否 | `100` | 每个会话保留的最近消息数，供 `get_history` 查询 |

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

| 字段 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| name | 否 | `default` | 路由名，出现在推送内容和日志中 |
| sessions | 否 | `["*"]` | 会话匹配规则 |
| webhook_url | 是 | 无 | Routine 的 Webhook 地址 |
| webhook_key | 否 | 无 | Routine 的 key，以 `Authorization: Bearer <key>` 发送 |
| owner_trigger | 否 | `to_me` | Owner 消息何时立即推送：`always` / `to_me` / `never` |
| flush_interval | 否 | 无 | 非 Owner 消息积压多少秒后推送 |
| flush_size | 否 | 无 | 非 Owner 消息积压多少条后推送 |
| max_pending | 否 | `100` | 积压消息上限，超出丢弃最旧的 |

推送时机：

- Owner 的消息：按路由的 `owner_trigger` 决定是否立即推送（并带上该会话中尚未推送的消息）。
  - `always`：Owner 任何发言都推送，适合私聊和特殊群。
  - `to_me`（默认）：仅 @bot、回复 bot 或私聊时推送，群里普通发言不推送。
  - `never`：Owner 也不触发。
- 其他人的消息：先积压，满 `flush_size` 条或第一条积压消息之后过了 `flush_interval` 秒时推送；两者都不设置时，只作为上下文等 Owner 触发。
- bot 自己发出的消息：只记入上下文，不触发推送。

## 🎉 使用

### Webhook 推送格式

```json
{
  "route": "groups",
  "trigger": "owner",
  "session": "group:123456",
  "session_name": "某某群",
  "messages": [
    {
      "session": "group:123456",
      "session_name": "某某群",
      "message_id": "1001",
      "time": "2026-10-10T18:00:00+08:00",
      "sender": {"user_id": "10000", "nickname": "Yan", "is_owner": true, "is_self": false},
      "to_me": false,
      "segments": [
        {"type": "text", "text": "看看这个"},
        {"type": "image", "url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=…&rkey=…", "sticker": false},
        {"type": "emoji", "id": "14", "name": "微笑"},
        {"type": "forward", "id": "7391..."}
      ]
    }
  ]
}
```

`trigger` 为 `owner` / `size` / `interval`。`session_name` 为群名（OneBot `get_group_info`，首次收到该群消息时获取并缓存）或私聊对象昵称。合并转发（聊天记录）只给出 `id`，需要时通过 MCP `get_forward_message` 查看。图片直接给原始链接，插件不缓存。QQ 图片链接里的 rkey 会过期，通过 MCP `get_image(url)` 查看或在 `send_message` 中转发时，插件会自动调用 `get_rkey` 重新签发（需要 NapCat / LLOneBot 等支持该扩展 API 的实现）。

### MCP 工具

| 工具 | 说明 |
|:-----:|:----:|
| `send_message(session, segments, reply_to?, self_id?)` | 发送消息，消息段类型有 `text` / `image`（`url` / `base64`）/ `emoji` / `sticker` / `at` / `at_all` |
| `get_history(session, limit)` | 会话最近消息，格式同 Webhook |
| `get_image(url, session?)` | 查看图片，QQ 链接自动续签 rkey |
| `list_sessions()` | 收到过消息的会话及名称 |
| `get_forward_message(forward_id, session)` | 查看合并转发（聊天记录）内容，嵌套转发同样只给 id |
| `list_emojis()` | QQ 内置表情 ID → 名称 |
| `search_stickers(query, session, limit)` | 搜索本地表情包（需 savepic） |
| `view_sticker(name, session)` | 查看表情包图片（需 savepic） |

### 开发

    uv sync
    uv run pytest
    uv run python bot.py
