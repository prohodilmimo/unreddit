import hashlib
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
        return self.__trigger.bot

    def set_reply_markup(self, value: InlineKeyboardMarkup) -> None:
        self.__reply_markup = value

    def __init__(self, trigger: Union[Message, InlineQuery],
                 text: Optional[str],
                 reply_markup: Optional[InlineKeyboardMarkup] = None,
                 parse_mode: Optional[str] = None):

        self.__trigger = trigger
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
        if isinstance(self.__trigger, Message):
            await self.__send_message(self.__trigger)

        elif isinstance(self.__trigger, InlineQuery):
            await self.__send_inline(self.__trigger)

    async def __send_message(self, message: Message):
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

    async def __send_inline(self, query: InlineQuery):
        results = []

        if self.__type is not None and self.__thumbnail is None:
            return

        elif self.__type == ContentType.VIDEO:
            results.append(self.__generate_query_result_video())

        elif self.__type == ContentType.PHOTO:
            results.append(self.__generate_query_result_photo())

        elif self.__type == ContentType.ANIMATION:
            results.append(self.__generate_query_result_animation())

        elif self.__type is None:
            for media in self.__payload:
                if media.thumb is None:
                    continue

                elif media.type == ContentType.VIDEO:
                    results.append(
                        self.__generate_query_result_video(media))

                elif media.type == ContentType.PHOTO:
                    results.append(
                        self.__generate_query_result_photo(media))

                elif media.type == ContentType.ANIMATION:
                    results.append(
                        self.__generate_query_result_animation(media))

        if not results:
            return

        try:
            await query.answer(results)

        except Exception as e:
            logging.getLogger().exception("", exc_info=e)

    def __generate_query_result_video(self, media: InputMedia = None
                                      ) -> InlineQueryResultVideo:
        if media is None:
            data_id = hashlib.md5(self.__fallback.encode()).hexdigest()

            return InlineQueryResultVideo(
                id=data_id,
                video_url=self.__payload,
                caption=self.__caption,
                reply_markup=self.__reply_markup,

                title=self.__caption,
                thumb_url=self.__thumbnail,
                mime_type="video/mp4"
            )

        else:
            data_id = hashlib.md5(media.media.encode()).hexdigest()

            return InlineQueryResultVideo(
                id=data_id,
                video_url=media.media,
                caption=media.caption,

                title=media.caption,
                thumb_url=media.thumb,
                mime_type="video/mp4"
            )

    def __generate_query_result_photo(self, media: InputMedia = None
                                      ) -> InlineQueryResultPhoto:
        if media is None:
            data_id = hashlib.md5(self.__fallback.encode()).hexdigest()

            return InlineQueryResultPhoto(
                id=data_id,
                photo_url=self.__payload,
                caption=self.__caption,
                reply_markup=self.__reply_markup,

                title=self.__caption,
                thumb_url=self.__thumbnail
            )

        else:
            data_id = hashlib.md5(media.media.encode()).hexdigest()

            return InlineQueryResultPhoto(
                id=data_id,
                photo_url=media.media,
                caption=media.caption,

                title=media.caption,
                thumb_url=media.thumb
            )

    def __generate_query_result_animation(self, media: InputMedia = None
                                          ) -> InlineQueryResultGif:
        if media is None:
            data_id = hashlib.md5(self.__fallback.encode()).hexdigest()

            return InlineQueryResultGif(
                id=data_id,
                gif_url=self.__payload,
                caption=self.__caption,
                reply_markup=self.__reply_markup,

                title=self.__caption,
                thumb_url=self.__thumbnail
            )

        else:
            data_id = hashlib.md5(media.media.encode()).hexdigest()

            return InlineQueryResultGif(
                id=data_id,
                gif_url=media.media,
                caption=media.caption,

                title=media.caption,
                thumb_url=media.thumb
            )


__all__ = ["Reply"]
