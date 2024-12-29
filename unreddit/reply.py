import hashlib
import logging
from typing import Union

from aiogram.types import (Message, InlineQuery, InlineKeyboardMarkup, ContentType, InputMedia,
                           InlineQueryResultGif, InlineQueryResultPhoto, InlineQueryResultVideo, InlineKeyboardButton,
                           InlineQueryResult)
from aiogram.utils.exceptions import BadRequest

from content import *


def _to_keyboard_markup(metadata: Metadata) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()

    for button in metadata.get_buttons():
        markup.insert(InlineKeyboardButton(button.text, url=button.url))

    return markup


class Reply:
    def __init__(self, trigger: Union[Message, InlineQuery],
                 content: Content,
                 metadata: Metadata):

        self.__trigger = trigger
        self.__content = content
        self.__metadata = metadata

    async def send(self):
        if isinstance(self.__trigger, Message):
            await _send_message(self.__trigger, self.__content, self.__metadata)

        elif isinstance(self.__trigger, InlineQuery) and isinstance(self.__content, Media):
            await _send_inline(self.__trigger, self.__content, self.__metadata)


async def _send_message(message: Message, content: Content, metadata: Metadata):
    reply_markup = _to_keyboard_markup(metadata)

    try:
        if isinstance(content, Text):
            await message.reply(content.payload,
                                parse_mode=content.parse_mode,
                                reply_markup=reply_markup)

        elif isinstance(content, Image):
            await message.reply_photo(content.payload,
                                      caption=content.caption,
                                      reply_markup=reply_markup)

        elif isinstance(content, Video):
            await message.reply_video(content.payload,
                                      caption=content.caption,
                                      reply_markup=reply_markup)

        elif isinstance(content, Animation):
            await message.reply_animation(content.payload,
                                          caption=content.caption,
                                          reply_markup=reply_markup)

        elif isinstance(content, Album):
            album_messages = await message.reply_media_group([_to_input_media(m) for m in content.payload])

            # TODO: make it work
            # if album_messages:
            #     await album_messages[0].edit_reply_markup(buttons)
            await album_messages[0].reply(content.caption,
                                          reply_markup=reply_markup)

    except BadRequest as e:
        if not isinstance(content, Media):
            logging.getLogger().warning(f"Message {content.payload} "
                                        f"has failed to send: {e}")

        else:
            await message.reply(content.get_embed_fallback_message(),
                                parse_mode="html",
                                reply_markup=reply_markup)

            logging.getLogger().warning(f"{type(content)} {content.fallback} "
                                        f"has failed to embed: {e}")


async def _send_inline(query: InlineQuery, content: Media, metadata: Metadata):
    reply_markup = _to_keyboard_markup(metadata)
    results = []

    if isinstance(content, Album):
        for media in content.payload:
            results.append(_to_query_result(media, reply_markup))

    else:
        results.append(_to_query_result(content, reply_markup))

    if not results:
        return

    try:
        await query.answer(results)

    except Exception as e:
        logging.getLogger().exception("", exc_info=e)


def _to_query_result(media: Media, reply_markup: InlineKeyboardMarkup = None) -> InlineQueryResult:
    data_id = hashlib.md5(media.payload.encode()).hexdigest()

    if isinstance(media, Video):
        return InlineQueryResultVideo(
            id=data_id,
            video_url=media.payload,
            caption=media.caption,

            title=media.caption,
            reply_markup=reply_markup,
            thumb_url=media.thumbnail,
            mime_type="video/mp4"
        )

    elif isinstance(media, Image):
        return InlineQueryResultPhoto(
            id=data_id,
            photo_url=media.payload,
            caption=media.caption,

            title=media.caption,
            reply_markup=reply_markup,
            thumb_url=media.thumbnail
        )

    elif isinstance(media, Animation):
        return InlineQueryResultGif(
            id=data_id,
            gif_url=media.payload,
            caption=media.caption,

            title=media.caption,
            reply_markup=reply_markup,
            thumb_url=media.thumbnail
        )

    else:
        raise ValueError()


def _to_input_media(media: Media) -> InputMedia:
    if isinstance(media, Video):
        return InputMedia(
            media=media.payload,
            thumb=media.thumbnail,
            caption=media.caption,
            type=ContentType.VIDEO
        )

    elif isinstance(media, Image):
        return InputMedia(
            media=media.payload,
            thumb=media.thumbnail,
            caption=media.caption,
            type=ContentType.PHOTO
        )

    elif isinstance(media, Animation):
        return InputMedia(
            media=media.payload,
            thumb=media.thumbnail,
            caption=media.caption,
            type=ContentType.ANIMATION
        )

    else:
        raise ValueError()


__all__ = ["Reply"]
