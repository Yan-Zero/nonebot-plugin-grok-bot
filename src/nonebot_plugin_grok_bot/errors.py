import functools
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from mcp.server.mcpserver.exceptions import ToolError
from nonebot import logger

P = ParamSpec("P")
R = TypeVar("R")


def expose_errors(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """mcp 默认隐藏工具内部异常的信息，这里转成 ToolError 让 Grok Bot 能看到原因并自行修正"""

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except ToolError:
            raise
        except Exception as e:
            logger.opt(exception=e).debug(f"MCP 工具 {fn.__name__} 执行失败")
            raise ToolError(f"{type(e).__name__}: {e}") from e

    return wrapper
