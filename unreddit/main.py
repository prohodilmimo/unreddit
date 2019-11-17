import logging
import re
from os import path
from typing import Dict
from urllib.parse import urlsplit, urlunsplit

import ujson
import uvloop
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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

        post_data = op["data"]["children"][0]["data"]

        title = post_data["title"]
        permalink = post_data["permalink"]
        sub = post_data["subreddit_name_prefixed"]
        author = "u/" + post_data["author"]

        buttons = InlineKeyboardMarkup()

        buttons.add(InlineKeyboardButton("Original Post", url=urlunsplit((scheme, netloc, permalink, None, None))),
                    InlineKeyboardButton(sub,             url=urlunsplit((scheme, netloc, sub, None, None))))

        post_hint = post_data.get("post_hint")
        is_video = post_data.get("is_video", False)

        if post_hint is None and not is_video:
            continue

        if is_video:
            video_url = post_data["secure_media"]["reddit_video"]["fallback_url"]

            await message.reply_video(video_url, caption=title,
                                      parse_mode="markdown",
                                      reply_markup=buttons)

        elif post_hint == "image":
            image_url = post_data["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")

            await message.reply_photo(image_url, caption=title,
                                      reply_markup=buttons)

        # Gfycat (and maybe some other) embeds
        elif post_hint == "rich:video":
            await message.reply(f"[🎬]({post_data['url']}) {title}",
                                parse_mode="markdown",
                                reply_markup=buttons)

        # Links
        elif post_hint == "link":
            await message.reply(f"[🔗]({post_data['url']}) {title}",
                                parse_mode="markdown",
                                reply_markup=buttons)


async def unr(message: Message):
    links = set()

    for sub in re.findall(r"r/\w+", message.text, re.I):
        try:
            async with message.bot.session.get(f"https://www.reddit.com/{sub}.json",
                                               allow_redirects=False) as response:
                if response.status == 200:
                    data = await response.json()

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
    dp.register_message_handler(unr, regexp=r"(^|\s+)r/\w+")

    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    uvloop.install()

    config_path = path.join(path.dirname(path.realpath(__file__)),
                            "config.json")

    with open(config_path, "r") as config_file:
        config = ujson.load(config_file)

    main(**config)
