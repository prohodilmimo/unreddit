import logging
import os
import re
from typing import Dict
from urllib.parse import urlsplit, urlunsplit

import ujson
import uvloop
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import WrongFileIdentifier, BadRequest
from aiohttp import ClientError


async def unlink(message: Message):
    urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        message.text
    )

    for url in urls:
        scheme, netloc, path, *_ = urlsplit(url)

        if not netloc.endswith("reddit.com"):
            continue

        url = urlunsplit((scheme, netloc, path, None, None))

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

            permalink = comment_data["permalink"]
            post_permalink = post_data["permalink"]
            sub = comment_data["subreddit_name_prefixed"]
            body = comment_data["body"]

            buttons = InlineKeyboardMarkup()

            buttons.add(InlineKeyboardButton("Comment",         url=urlunsplit((scheme, netloc, permalink, None, None))),
                        InlineKeyboardButton("Original Post",   url=urlunsplit((scheme, netloc, post_permalink, None, None))),
                        InlineKeyboardButton(sub,               url=urlunsplit((scheme, netloc, sub, None, None))))

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
        permalink = post_data["permalink"]
        sub = post_data["subreddit_name_prefixed"]
        author = "u/" + post_data["author"]

        buttons = InlineKeyboardMarkup()

        buttons.add(InlineKeyboardButton("Original Post", url=urlunsplit((scheme, netloc, permalink, None, None))),
                    InlineKeyboardButton(sub,             url=urlunsplit((scheme, netloc, sub, None, None))))

        post_hint = post_data.get("post_hint")
        is_video = post_data.get("is_video", False)
        is_nsfw = post_data.get("over_18", False)

        if post_hint is None and not is_video:
            continue

        if is_video:
            video_url = post_data["secure_media"]["reddit_video"]["fallback_url"]

            try:
                await message.reply_video(video_url, caption=title,
                                          reply_markup=buttons)

            except WrongFileIdentifier:
                await message.reply("🚫 Telegram wasn't able to embed the video",
                                    reply_markup=buttons)

        elif post_hint == "image":
            image_url = post_data["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")

            if re.search(r"\.gif", image_url, re.I):
                try:
                    image_url = post_data["preview"]["images"][0]["variants"]["gif"]["source"]["url"]
                    await message.reply_animation(image_url, caption=title,
                                                  reply_markup=buttons)
                    return

                except BadRequest:
                    await message.reply("🚫 Telegram wasn't able to embed the animation",
                                        reply_markup=buttons)
                    return

                except (IndexError, KeyError):
                    pass

            await message.reply_photo(image_url, caption=title,
                                      reply_markup=buttons)

        elif is_nsfw and post_hint in ("rich:video", "link"):
            await message.reply(f"<a href=\"{post_data['url']}\">🔞</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)

        # Gfycat (and maybe some other) embeds
        elif post_hint == "rich:video":
            await message.reply(f"<a href=\"{post_data['url']}\">🎬</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)

        # Links
        elif post_hint == "link":
            await message.reply(f"<a href=\"{post_data['url']}\">🔗</a> {title}",
                                parse_mode="html",
                                reply_markup=buttons)


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


def main(token: str, headers: Dict):
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=token)
    bot.session._default_headers = headers

    dp = Dispatcher(bot)

    dp.register_message_handler(unlink, regexp=r"reddit.com/r/\w+/comments")
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
