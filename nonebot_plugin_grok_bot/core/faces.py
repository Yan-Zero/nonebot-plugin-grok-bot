import json
from pathlib import Path

_QFACE = Path(__file__).parent.parent / "resources" / "qface.json"

# QQ 内置表情（小黄脸）ID -> 名称，来自 nonebot-plugin-chatgpt-vision
FACES: dict[str, str] = json.loads(_QFACE.read_text(encoding="utf-8"))
