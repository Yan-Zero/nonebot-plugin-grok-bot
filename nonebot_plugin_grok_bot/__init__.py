from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")

from . import mcp_server as mcp_server  # noqa: E402
from . import webhook as webhook  # noqa: E402
from .config import Config  # noqa: E402

__plugin_meta__ = PluginMetadata(
    name="Grok Bot",
    description="通过 MCP Server 让 Grok Bot 发送消息，并将收到的消息推送到 Grok Bot 的 Routine Webhook",
    usage="配置 GROK_BOT_ROUTES / GROK_BOT_MASTERS / GROK_BOT_MCP_TOKEN 后，将 MCP 端点提供给 Grok Bot",
    type="application",
    homepage="https://github.com/Yan-Zero/nonebot-plugin-grok-bot",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)
