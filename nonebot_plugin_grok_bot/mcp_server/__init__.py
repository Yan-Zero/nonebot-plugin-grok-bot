"""Grok Bot -> NoneBot：在 NoneBot 的 ASGI 应用上挂载 MCP Server"""

from contextlib import AsyncExitStack

from mcp.server.transport_security import TransportSecuritySettings
from nonebot import get_app, get_driver, get_plugin_config, logger
from nonebot.drivers import ASGIMixin
from starlette.types import ASGIApp

from ..config import Config
from . import stickers
from . import tools as tools
from .auth import BearerAuth
from .server import mcp as mcp

driver = get_driver()
config = get_plugin_config(Config)

if not isinstance(driver, ASGIMixin):
    raise RuntimeError("nonebot-plugin-grok-bot 需要 ASGI 驱动器（如 ~fastapi）来挂载 MCP Server")

_LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
_security = None
if hosts := config.grok_bot_mcp_allowed_hosts:
    # 自定义 Host 白名单时需要显式带上 localhost，否则本机调试会被拒绝
    _security = TransportSecuritySettings(
        allowed_hosts=[*_LOCAL_HOSTS, *hosts],
        allowed_origins=[f"http://{h}" for h in _LOCAL_HOSTS] + [f"https://{h}" for h in hosts],
    )
_app: ASGIApp = mcp.streamable_http_app(host=str(driver.config.host), transport_security=_security)
if config.grok_bot_mcp_token:
    _app = BearerAuth(_app, config.grok_bot_mcp_token)
get_app().mount(config.grok_bot_mcp_prefix, _app)

# 挂载的子应用不会触发自身 lifespan，需要手动管理 session manager
_stack = AsyncExitStack()


@driver.on_startup
async def _() -> None:
    stickers.register_tools()
    await _stack.enter_async_context(mcp.session_manager.run())
    logger.info(f"Grok Bot MCP Server 已挂载于 {config.grok_bot_mcp_prefix}/mcp")


@driver.on_shutdown
async def _() -> None:
    await _stack.aclose()
