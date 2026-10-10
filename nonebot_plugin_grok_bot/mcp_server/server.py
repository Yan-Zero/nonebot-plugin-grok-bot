from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    name="nonebot-grok-bot",
    instructions=(
        "通过这些工具向聊天平台发送消息。会话用 `group:<群号>` / `private:<QQ号>` 表示，"
        "与 Webhook 推送中的 `session` 字段一致。消息由多个消息段组成，可图文混排，"
        "可使用 QQ 内置表情（list_emojis）和本地表情包（search_stickers）。"
        "收到的消息中的合并转发（聊天记录）只给出 id，需要时用 get_forward_message 查看内容。"
    ),
)
