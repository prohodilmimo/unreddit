import logging
import os
import re
from typing import Dict, List, Pattern, Optional
from urllib.parse import urlsplit, urlunsplit

import ujson
import uvloop
from aiogram import Bot, Dispatcher, executor
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           InputMedia)
from aiogram.utils.exceptions import BadRequest
from aiohttp import ClientError


def get_urls(text: str, domain_constraint: Pattern) -> str:
    urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text
    )

    for url in urls:
        scheme, netloc, path, *_ = urlsplit(url)

        if not re.search(domain_constraint, netloc):
            continue

        yield urlunsplit((scheme, netloc, path, None, None))


async def unlink(message: Message):
    for url in get_urls(message.text, re.compile(r"reddit\.com$")):
        try:
            async with message.bot.session.get(url + ".json") as response:
                post = await response.json(loads=ujson.loads)

        except ClientError as e:
            logging.getLogger().error(e)
            return

        op, comments = post

        path = [part for part in path.split("/") if part]

        post_data = op["data"]["children"][0]["data"]

        if len(path) == 6 or len(path) == 4:  # is a link to the comment
            comment_data = comments["data"]["children"][0]["data"]

            body = comment_data["body"]

            buttons = generate_buttons(url, post_data, comment_data)

            if len(body) > 1024:
                try:
                    body = body[:(body.rindex("\n", 0, 1021) + 1)] + "\[…]"

                except ValueError:
                    try:
                        body = body[:(body.rindex(". ", 0, 1020) + 1)] + " \[…]"

                    except ValueError:
                        try:
                            body = body[:(body.rindex(" ", 0, 1021) + 1)] + "\[…]"

                        except ValueError:
                            body = body[:1019] + "\n\n\[…]"

            await message.reply(body,
                                parse_mode="markdown",
                                reply_markup=buttons)
            return

        if "crosspost_parent_list" in post_data:
            post_data = post_data["crosspost_parent_list"][0]

        title = post_data["title"]

        buttons = generate_buttons(url, post_data)

        post_hint = post_data.get("post_hint")
        is_reddit_media = post_data.get("is_reddit_media_domain", False)
        is_video = post_data.get("is_video", False)
        is_nsfw = post_data.get("over_18", False)

        if post_hint is None and not is_reddit_media:
            continue

        if is_video:
            video_url = post_data["secure_media"]["reddit_video"]["fallback_url"]

            await send_video(video_url, message, title, buttons)

        elif post_hint == "image" or (post_hint is None and is_reddit_media):
            image_url = post_data["url"]

            is_gif = re.search(r"\.gif", image_url, re.I)

            if post_hint is not None and is_gif:
                image_url = post_data["preview"]["images"][0]["variants"]["gif"]["source"]["url"]

            elif post_hint is not None:
                image_url = post_data["preview"]["images"][0]["source"]["url"]

            image_url = image_url.replace("&amp;", "&")

            if is_gif:
                await send_animation(image_url, message, title, buttons)

            else:
                await send_image(image_url, message, title, buttons)

        elif re.search("imgur\.com", post_data['url']):
            try:
                await send_imgur(post_data['url'], message, title, buttons)

            except ValueError:
                await message.reply(f"<a href=\"{post_data['url']}\">🔗</a> {title}",
                                    parse_mode="html",
                                    reply_markup=buttons)

        elif re.search("gfycat\.com", post_data['url']):
            try:
                await send_gfycat(post_data['url'], message, title, buttons)

            except ValueError:
                await message.reply(f"<a href=\"{post_data['url']}\">🔗</a> {title}",
                                    parse_mode="html",
                                    reply_markup=buttons)

        elif is_nsfw and post_hint == "rich:video":
            await message.reply(f"<a href=\"{post_data['url']}\">🔞</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)

        # Video embeds
        elif post_hint == "rich:video":
            await message.reply(f"<a href=\"{post_data['url']}\">🎬</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)

        # Links
        elif post_hint == "link":
            await message.reply(f"<a href=\"{post_data['url']}\">🔗</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)


def generate_buttons(url: str, post_data: Dict, comment_data: Dict = None
                     ) -> InlineKeyboardMarkup:
    scheme, netloc, path, *_ = urlsplit(url)

    permalink = post_data["permalink"]
    sub = post_data["subreddit_name_prefixed"]

    buttons = InlineKeyboardMarkup()

    buttons.add(InlineKeyboardButton("Original Post", url=urlunsplit((scheme, netloc, permalink, None, None))),
                InlineKeyboardButton(sub,             url=urlunsplit((scheme, netloc, sub, None, None))))

    if comment_data is None:
        author = "u/" + post_data["author"]

    else:
        comment_permalink = comment_data["permalink"]
        author = "u/" + comment_data["author"]

        buttons.add(InlineKeyboardButton("Comment", url=urlunsplit((scheme, netloc, comment_permalink, None, None))))

    return buttons


async def send_gfycat(url, message: Message, title: Optional[str],
                      buttons: Optional[InlineKeyboardMarkup]) -> None:
    scheme, netloc, path, *_ = urlsplit(url)

    post_id, *_ = path[1:].split("-")

    async with message.bot.session.get(f"https://api.gfycat.com/v1/gfycats/{post_id}") as response:
        if response.status != 200:
            raise ValueError

        data = await response.json(loads=ujson.loads)

    if title is None:
        title = data["gfyItem"]["title"] or None

    if data["gfyItem"]["hasAudio"]:
        await send_video(data["gfyItem"]["mp4Url"], message, title, buttons)

    else:
        await send_animation(data["gfyItem"]["gifUrl"], message, title, buttons)


async def send_imgur(url, message: Message, title: Optional[str],
                     buttons: Optional[InlineKeyboardMarkup]) -> None:
    scheme, netloc, path, *_ = urlsplit(url)

    if re.match(r"/gallery/\w+", path):
        *_, post_id = path.split("/")
        async with message.bot.session.get(f"https://api.imgur.com/3/album/{post_id}") as response:
            if response.status != 200:
                raise ValueError

            data = await response.json(loads=ujson.loads)

        media = []

        for image in data["data"]["images"]:
            if image["title"] and image["description"]:
                caption = f"{image['title']}\n\n{image['description']}"

            elif image["title"]:
                caption = image["title"]

            elif image["description"]:
                caption = image["description"]

            else:
                caption = None

            if image["type"] in ("image/gif", "video/mp4"):
                media.append(
                    InputMedia(media=image["mp4"],
                               type="video",
                               caption=caption)
                )

            elif image["type"] in ("image/png", "image/jpeg"):
                media.append(
                    InputMedia(media=image["link"],
                               type="photo",
                               caption=caption)
                )

        if title is None:
            title = data["data"]["title"] or None

        await send_album(media, url, message, title, buttons)

    else:
        post_id, *_ = path[1:].split(".")

        async with message.bot.session.get(f"https://api.imgur.com/3/image/{post_id}") as response:
            if response.status != 200:
                raise ValueError

            data = await response.json(loads=ujson.loads)

        if title is None:
            title = data["data"]["title"] or None

        if data["data"]["type"] in ("image/gif", "video/mp4"):
            await send_video(data["data"]["mp4"], message, title, buttons)

        elif data["data"]["type"] in ("image/png", "image/jpeg"):
            await send_image(data["data"]["link"], message, title, buttons)


async def send_album(media: List[InputMedia], fallback_url: str,
                     message: Message, title: str,
                     buttons: InlineKeyboardMarkup) -> None:
    try:
        album_messages = await message.reply_media_group(media)

        # TODO: make it work
        # if album_messages:
        #     await album_messages[0].edit_reply_markup(buttons)
        await album_messages[0].reply(title, reply_markup=buttons)

    except BadRequest as e:
        await message.reply(f"<a href=\"{fallback_url}\">🔗</a> {title}\n\n"
                            f"[Telegram wasn't able to embed the album]",
                            parse_mode="html",
                            reply_markup=buttons)

        logging.getLogger().warning(f"Album {fallback_url} "
                                    f"has failed to embed: {e}")


async def send_animation(animation_url: str, message: Message, title: str,
                         buttons: InlineKeyboardMarkup) -> None:
    try:
        await message.reply_animation(animation_url, caption=title,
                                      reply_markup=buttons)
        return

    except BadRequest as e:
        await message.reply(f"<a href=\"{animation_url}\">🎬 {title}</a>\n\n"
                            f"[Telegram wasn't able to embed the animation]",
                            parse_mode="html",
                            reply_markup=buttons)
        logging.getLogger().warning(f"Animation {animation_url} "
                                    f"has failed to embed: {e}")
        return


async def send_video(video_url: str, message: Message, title: str,
                     buttons: InlineKeyboardMarkup) -> None:
    try:
        await message.reply_video(video_url, caption=title,
                                  reply_markup=buttons)

    except BadRequest as e:
        await message.reply(f"<a href=\"{video_url}\">🎬 {title}</a>\n\n"
                            f"[Telegram wasn't able to embed the video]",
                            parse_mode="html",
                            reply_markup=buttons)
        logging.getLogger().warning(f"Video {video_url} "
                                    f"has failed to embed: {e}")


async def send_image(image_url: str, message: Message, title: str,
                     buttons: InlineKeyboardMarkup) -> None:
    try:
        await message.reply_photo(image_url, caption=title,
                                  reply_markup=buttons)

    except BadRequest as e:
        await message.reply(f"<a href=\"{image_url}\">🖼 {title}</a>\n\n"
                            f"[Telegram wasn't able to embed the image]",
                            parse_mode="html",
                            reply_markup=buttons)
        logging.getLogger().warning(f"Image {image_url} "
                                    f"has failed to embed: {e}")


async def unr(message: Message):
    links = set()

    for sub in re.findall(r"r/\w+", message.text, re.I):
        try:
            async with message.bot.session.get(f"https://www.reddit.com/{sub}.json",
                                               allow_redirects=False) as response:
                if response.status == 200:
                    links.add(f"[{sub}](https://www.reddit.com/{sub})")

        except ClientError as e:
            logging.getLogger().error(e)
            return

    if links:
        await message.reply("\n".join(links), parse_mode="markdown",
                            disable_web_page_preview=True)


def main(token: str, headers: Dict, imgur: Dict):
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=token)

    headers["Authorization"] = f"Client-ID {imgur.get('client_id')}"

    bot.session._default_headers = headers

    dp = Dispatcher(bot)

    dp.register_message_handler(unlink, regexp=r"reddit.com/(r|u|user)/\w+/comments")
    dp.register_message_handler(unlink, regexp=r"reddit.com/comments")
    dp.register_message_handler(unr, regexp=r"(^|\s+)r/\w+")

    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    uvloop.install()

    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "config.json")

    with open(config_path, "r") as config_file:
        config = ujson.load(config_file)

    main(**config)
