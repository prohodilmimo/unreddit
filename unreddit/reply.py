import logging
from typing import Optional, List, Union

from aiogram import Bot
from aiogram.types import *
from aiogram.utils.exceptions import BadRequest


def trim_text(text: str, limit=1024) -> str:
    if len(text) <= limit:
        return text

    try:
        return text[:(text.rindex("\n", 0, limit - 3) + 1)] + "\[…]"

    except ValueError:
        try:
            return text[:(text.rindex(". ", 0, limit - 4) + 1)] + " \[…]"

        except ValueError:
            try:
                return text[:(text.rindex(" ", 0, limit - 3) + 1)] + "\[…]"

            except ValueError:
                return text[:1019] + "\n\n\[…]"


class Reply:
    @property
    def bot(self) -> Bot:
        return self.__message.bot

    def set_reply_markup(self, value: InlineKeyboardMarkup) -> None:
        self.__reply_markup = value

    def __init__(self, message: Message,
                 text: Optional[str],
                 reply_markup: Optional[InlineKeyboardMarkup] = None,
                 parse_mode: Optional[str] = None):

        self.__message = message
        self.__reply_markup = reply_markup

        self.__caption: Optional[str] = None
        self.__type: ContentType = ContentType.UNKNOWN
        self.__payload: Union[None, str, List[InputMedia]] = None
        self.__fallback: Optional[str] = None
        self.__thumbnail: Optional[str] = None

        if text is not None:
            self.attach_text(text)

        self.__parse_mode = parse_mode

    def attach_text(self, text: str) -> None:
        if text is not None:
            text = trim_text(text)

        self.__caption = text
        self.__type = ContentType.TEXT
        self.__payload = text
        self.__fallback = text

    def attach_album(self, media: List[InputMedia], fallback_url: str,
                     caption: Optional[str]) -> None:
        self.__caption = caption
        self.__type = None
        self.__payload = media
        self.__fallback = fallback_url

    def attach_animation(self, url: str, thumbnail_url: Optional[str],
                         caption: Optional[str]) -> None:
        self.__caption = caption
        self.__type = ContentType.ANIMATION
        self.__payload = url
        self.__fallback = url
        self.__thumbnail = thumbnail_url

    def attach_video(self, url: str, thumbnail_url: Optional[str],
                     caption: Optional[str]) -> None:
        self.__caption = caption
        self.__type = ContentType.VIDEO
        self.__payload = url
        self.__fallback = url
        self.__thumbnail = thumbnail_url

    def attach_image(self, url: str, thumbnail_url: Optional[str],
                     caption: Optional[str]) -> None:
        self.__caption = caption
        self.__type = ContentType.PHOTO
        self.__payload = url
        self.__fallback = url
        self.__thumbnail = thumbnail_url or url

    def attach_link(self, url: str, caption: str, icon: str = "🔗") -> None:
        self.__caption = caption
        self.__type = ContentType.TEXT
        self.__payload = f"<a href=\"{url}\">{icon}</a> {caption}"
        self.__fallback = url

    async def send(self):
        message = self.__message

        try:
            if self.__type == ContentType.TEXT:
                await message.reply(self.__payload,
                                    parse_mode=self.__parse_mode,
                                    reply_markup=self.__reply_markup)

            elif self.__type == ContentType.PHOTO:
                await message.reply_photo(self.__payload,
                                          caption=self.__caption,
                                          reply_markup=self.__reply_markup)

            elif self.__type == ContentType.VIDEO:
                await message.reply_video(self.__payload,
                                          caption=self.__caption,
                                          reply_markup=self.__reply_markup)

            elif self.__type == ContentType.ANIMATION:
                await message.reply_animation(self.__payload,
                                              caption=self.__caption,
                                              reply_markup=self.__reply_markup)

            elif self.__type is None:
                album_messages = await message.reply_media_group(self.__payload)

                # TODO: make it work
                # if album_messages:
                #     await album_messages[0].edit_reply_markup(buttons)
                await album_messages[0].reply(self.__caption,
                                              reply_markup=self.__reply_markup)

        except BadRequest as e:
            if self.__type == ContentType.TEXT:
                logging.getLogger().warning(f"Message {self.__payload} "
                                            f"has failed to send: {e}")

            else:
                descriptor, icon = self.CONTENT_TYPE_DESCRIPTORS[self.__type]

                await message.reply(f"<a href=\"{self.__fallback}\">{icon} {self.__caption}</a>\n\n"
                                    f"[Telegram wasn't able to embed the {descriptor}]",
                                    parse_mode="html",
                                    reply_markup=self.__reply_markup)

                logging.getLogger().warning(f"{descriptor.capitalize()} {self.__fallback} "
                                            f"has failed to embed: {e}")

    CONTENT_TYPE_DESCRIPTORS = {
        ContentType.PHOTO:      ("image", "🖼"),
        ContentType.VIDEO:      ("video", "🎬"),
        ContentType.ANIMATION:  ("animation", "🎬"),
        None:                   ("album", "🔗")
    }


__all__ = ["Reply"]
