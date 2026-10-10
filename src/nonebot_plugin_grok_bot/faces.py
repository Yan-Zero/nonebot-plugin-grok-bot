import json
from pathlib import Path

# QQ 内置表情（小黄脸）ID -> 名称，来自 nonebot-plugin-chatgpt-vision
FACES: dict[str, str] = json.loads((Path(__file__).parent / "qface.json").read_text(encoding="utf-8"))
