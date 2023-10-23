import logging
import os
import re
from typing import Dict, Union
from urllib.parse import urlsplit, urlunsplit

import ujson
import uvloop
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineQuery
from aiohttp import ClientError, ClientSession

from api_reply import *


def clean_up_url(url):
    scheme, netloc, path, *_ = urlsplit(url)
    return urlunsplit((scheme, netloc, path, None, None))


def get_urls(text: str) -> str:
    urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text
    )

    for url in urls:
        yield clean_up_url(url)


async def resolve_opaque_share_url(session: ClientSession, url: str) -> str:
    async with session.head(url, raise_for_status=True, allow_redirects=False) as response:
        return clean_up_url(response.headers.get("Location"))


async def unreddit(trigger: Union[Message, InlineQuery]):
    if isinstance(trigger, Message):
        text = trigger.text

    elif isinstance(trigger, InlineQuery):
        text = trigger.query

    else:
        return

    for url in get_urls(text):
        match = APIReply.REDDIT_REGEXP.search(url)

        if not match:
            continue

        if 's' in match.groups():  # is an opaque share link
            url = await resolve_opaque_share_url(trigger.bot.session, url)

        scheme, netloc, path, *_ = urlsplit(url)

        path = [part for part in path.split("/") if part]

        if len(path) == 6 or len(path) == 4:  # is a link to the comment
            try:
                reply = RedditCommentReply(trigger)

            except ValueError:
                continue

            try:
                await reply.attach_from_reddit_comment(url)
                await reply.send()

            except ClientError as e:
                logging.getLogger().error(e)
                continue

        else:
            reply = APIReply(trigger)

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
                    data = await response.json()

                    posts: list = data["data"]["children"]

                    if posts:
                        sub = posts[0]["data"]["subreddit_name_prefixed"]

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

    dp.register_inline_handler(unreddit)

    executor.start_polling(dp, skip_updates=True)


if __name__ == '__main__':
    uvloop.install()

    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               "config.json")

    with open(config_path, "r") as config_file:
        config = ujson.load(config_file)

    main(**config)
