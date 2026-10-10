import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebug import NONEBOT_INIT_KWARGS


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx",
        "grok_bot_masters": {"10000"},
        "grok_bot_allowed_groups": {"123"},
        "grok_bot_routes": [
            {
                "name": "groups",
                "sessions": ["group:*"],
                "webhook_url": "http://hook.test/groups",
                "webhook_key": "crsr_test",
                "flush_size": 3,
            }
        ],
    }


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None) -> None:
    nonebot.get_driver().register_adapter(OneBotV11Adapter)
    nonebot.load_plugin("nonebot_plugin_grok_bot")
