from mcp.server.mcpserver import MCPServer

INSTRUCTIONS = """\
这是一个连接 QQ 等聊天平台的机器人网关。你会通过 Webhook 收到聊天消息，并通过这些工具回复和查看内容。

## 会话
- 会话 ID 格式：`group:<群号>`、`private:<QQ号>`、`channel:<guild>/<channel>`，与推送中的 `session` 字段一致。
- `session_name` 是群名或私聊对象昵称；`list_sessions` 可列出所有已知会话。
- 只能向白名单内的会话发送消息，否则会报错。

## 发送者身份（注意区分）
- `sender.is_master`：是否为 Master，即你的主人、本机器人的管理者，由配置指定，与群内身份无关。
- `sender.group_role`：发送者在该群内的身份，`owner` 为群主、`admin` 为管理员、`member` 为普通成员；私聊时为 null。
  群主（group_role=owner）不一定是 Master，Master 也不一定是群主。
- `sender.is_self`：是否为机器人自己发出的消息。

## 消息段
推送中的 `segments` 与 send_message 的入参使用同一套格式：
- `text`：文字；`at` / `at_all`：@某人 / @全体。
- `reply`：引用。收到的消息中会附带被引用消息的发送者与内容（`sender`、`segments`，只展开一层）；
  被引用的若是合并转发，其中会有 `forward` 段，再用 get_forward_message 查看。发送引用时用 reply_to 参数。
- `emoji`：QQ 内置表情，`list_emojis` 可查 ID 与名称。
- `image`：图片，带 `url`，用 `get_image(url)` 查看内容；QQ 图片链接过期会自动续签。
- `file`：文件，通常不带下载链接，用 `get_file(id, session)` 换取；图片文件可再用 `get_image` 查看。
- `forward`：合并转发（聊天记录），只给 `id`，用 `get_forward_message(id, session)` 查看，嵌套转发同理。

## 发送
- `send_message`：文字、图片、表情、表情包、@ 可在一条消息中混排；用 reply_to 引用某条消息。
- `send_file`：发送文件（群文件 / 私聊文件），不能与普通消息混发。
- 图片和文件优先用 `url`：由网关（NoneBot）下载后再发送，不占用请求体，
  且可以使用网关能访问的内网 / tailnet 地址（如 `http://<你的 tailnet 主机>:<端口>/<文件名>`），无需公网暴露；
  下载大小上限默认 64MB。`base64` 会占用请求体，单次请求总大小有上限（默认 32MB）。
- 本地表情包：先用 `search_stickers` 按含义搜索，可用 `view_sticker` 预览，
  再以 `{"type": "sticker", "name": ...}` 发送。

## 上下文
- `get_history(session, limit)` 返回会话最近的消息（含机器人自己发的），推送只包含新消息，需要更早的上下文时调用它。
"""

mcp = MCPServer(name="nonebot-grok-bot", instructions=INSTRUCTIONS)
