"""send_message 的消息段入参模型，以及到 UniMessage 消息段的转换"""

import base64
from typing import Annotated, Literal

from nonebot.adapters import Bot
from nonebot_plugin_alconna.uniseg import At, AtAll, Emoji, Image, Segment, Text
from pydantic import BaseModel, Field

from ..core.faces import FACES
from ..core.media import download
from . import stickers


class TextSegment(BaseModel):
    type: Literal["text"]
    text: str


class ImageSegment(BaseModel):
    type: Literal["image"]
    url: str | None = Field(
        default=None,
        description="图片链接，由网关下载后发送（可用内网 / tailnet 地址；QQ 图片链接会自动续签 rkey）",
    )
    base64: str | None = Field(default=None, description="base64 编码的图片数据")


class EmojiSegment(BaseModel):
    type: Literal["emoji"]
    id: str = Field(description="QQ 内置表情 ID，见 list_emojis")


class StickerSegment(BaseModel):
    type: Literal["sticker"]
    name: str = Field(description="本地表情包名称，见 search_stickers")


class AtSegment(BaseModel):
    type: Literal["at"]
    user_id: str


class AtAllSegment(BaseModel):
    type: Literal["at_all"]


OutSegment = Annotated[
    TextSegment | ImageSegment | EmojiSegment | StickerSegment | AtSegment | AtAllSegment,
    Field(discriminator="type"),
]


async def to_segment(seg: OutSegment, session: str, bot: Bot) -> Segment:
    match seg:
        case TextSegment(text=text):
            return Text(text)
        case EmojiSegment(id=id_):
            return Emoji(id_, FACES.get(id_))
        case AtSegment(user_id=user_id):
            return At("user", user_id)
        case AtAllSegment():
            return AtAll()
        case StickerSegment(name=name):
            return await stickers.load(name, session, bot)
        case ImageSegment(url=str(url)):
            # 由 NoneBot 下载后以原始数据发送，协议端无需能访问该 url
            return Image(raw=await download(url, bot))
        case ImageSegment(base64=str(b64)):
            return Image(raw=base64.b64decode(b64))
        case ImageSegment():
            raise ValueError("image 消息段需要 url 或 base64 之一")
    raise ValueError(f"不支持的消息段：{seg!r}")
