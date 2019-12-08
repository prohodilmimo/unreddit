import logging
import os
import re
from typing import Dict
from urllib.parse import urlsplit, urlunsplit

import ujson
import uvloop
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message
from aiohttp import ClientError

from unreddit.api_reply import *


def get_urls(text: str) -> str:
    urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text
    )

    for url in urls:
        scheme, netloc, path, *_ = urlsplit(url)

        yield urlunsplit((scheme, netloc, path, None, None))


async def unreddit(message: Message):
    for url in get_urls(message.text):
        if not APIReply.REDDIT_REGEXP.search(url):
            continue

        scheme, netloc, path, *_ = urlsplit(url)

        path = [part for part in path.split("/") if part]

        if len(path) == 6 or len(path) == 4:  # is a link to the comment
            reply = RedditCommentReply(message)

            try:
                await reply.attach_from_reddit_comment(url)
                await reply.send()

            except ClientError as e:
                logging.getLogger().error(e)
                continue

        else:
            reply = APIReply(message)

            try:
                await reply.attach_from_reddit(url)

            except ClientError as e:
                logging.getLogger().error(e)
                continue

            except MediaNotFoundError:
                continue

            await reply.send()


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


def main(token: str, reddit: Dict, imgur: Dict, gfycat: Dict):
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=token)
    headers = reddit["headers"]

    headers["Authorization"] = f"Client-ID {imgur.get('client_id')}"

    bot.session._default_headers = headers

    dp = Dispatcher(bot)

    dp.register_message_handler(unreddit, regexp=APIReply.REDDIT_REGEXP)
    dp.register_message_handler(unr, regexp=r"(^|\s+)r/\w+")

    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    uvloop.install()

    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               "config.json")

    with open(config_path, "r") as config_file:
        config = ujson.load(config_file)

    main(**config)
