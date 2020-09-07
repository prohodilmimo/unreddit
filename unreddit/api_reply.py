import re
from typing import Dict, Union
from urllib.parse import urlsplit, urlunsplit

import ujson
from aiogram.types import *
from aiohttp import ClientError

from reply import Reply


class MediaNotFoundError(Exception):
    pass


class APIReply(Reply):
    REDDIT_REGEXP = re.compile(r"reddit\.com(/(r|u|user)/\w+/|/)comments")
    IMGUR_REGEXP = re.compile(r"imgur\.com")
    GFYCAT_REGEXP = re.compile(r"gfycat\.com")

    def __init__(self, trigger: Union[Message, InlineQuery]):
        Reply.__init__(self, trigger, None, None, "html")

    async def attach_from_reddit(self, url: str) -> None:
        async with self.bot.session.get(url + ".json",
                                        raise_for_status=True) as response:
            data = await response.json(loads=ujson.loads)

        op, comments = data

        post_data = op["data"]["children"][0]["data"]

        title = post_data.get("title", None)
        self.set_reply_markup(generate_reddit_buttons(url, post_data))

        if "crosspost_parent_list" in post_data:
            post_data = post_data["crosspost_parent_list"][0]

        post_hint = post_data.get("post_hint")

        thumbnail = post_data.get("thumbnail", None)

        is_reddit_media = post_data.get("is_reddit_media_domain", False)
        is_gallery = post_data.get("media_metadata") is not None
        is_link_to_imgur = self.IMGUR_REGEXP.search(post_data['url']) is not None
        is_link_to_gfycat = self.GFYCAT_REGEXP.search(post_data['url']) is not None
        is_video = post_data.get("is_video", False)
        is_nsfw = post_data.get("over_18", False)

        if not thumbnail or thumbnail == "default":
            thumbnail = None

        if post_hint is None and (not is_reddit_media and
                                  not is_gallery and
                                  not is_link_to_imgur and
                                  not is_link_to_gfycat):
            raise MediaNotFoundError

        if is_video:
            try:
                thumbnail = post_data["preview"]["images"][0]["resolutions"][0]["url"]
            except (IndexError, KeyError):
                pass

            if thumbnail:
                thumbnail = thumbnail.replace("&amp;", "&")

            self.attach_video(post_data["secure_media"]["reddit_video"]["fallback_url"],
                              thumbnail,
                              title)

        elif is_gallery:
            media = []

            for image in post_data["media_metadata"].values():
                if image["status"] != "valid":
                    continue

                if image["m"] in ("image/png", "image/jpg"):
                    media.append(
                        InputMedia(media=image["s"]["u"].replace("&amp;", "&"),
                                   thumb=None,
                                   type=ContentType.PHOTO)
                    )

                elif image["m"] == "image/gif":
                    media.append(
                        InputMedia(media=image["s"]["u"].replace("&amp;", "&"),
                                   thumb=None,
                                   type=ContentType.ANIMATION)
                    )

            self.attach_album(media,
                              post_data["url"],
                              title)

        elif post_hint == "image" or (post_hint is None and is_reddit_media):
            image_url = post_data["url"]

            is_gif = re.search(r"\.gif", image_url, re.I)

            if post_hint is not None and is_gif:
                image_url = post_data["preview"]["images"][0]["variants"]["gif"]["source"]["url"]

            elif post_hint is not None:
                image_url = post_data["preview"]["images"][0]["source"]["url"]
                thumbnail = post_data["preview"]["images"][0]["resolutions"][0]["url"]

            image_url = image_url.replace("&amp;", "&")

            if thumbnail:
                thumbnail = thumbnail.replace("&amp;", "&")

            if is_gif:
                self.attach_animation(image_url,
                                      thumbnail,
                                      title)

            else:
                self.attach_image(image_url,
                                  thumbnail,
                                  title)

        elif is_link_to_imgur:
            try:
                await self.attach_from_imgur(post_data['url'])

                self.set_caption(title)

            except ClientError:
                self.attach_link(post_data["url"], title, icon="🖼")

        elif is_link_to_gfycat:
            try:
                await self.attach_from_gfycat(post_data['url'])

                self.set_caption(title)

            except ClientError:
                self.attach_link(post_data["url"], title, icon="🎬")

        # Video embeds
        elif post_hint == "rich:video":
            if is_nsfw:
                self.attach_link(post_data["url"], title, icon="🔞")

            else:
                self.attach_link(post_data["url"], title, icon="🎬")

        # Links
        elif post_hint == "link":
            self.attach_link(post_data["url"], title)

        else:
            raise MediaNotFoundError

    async def attach_from_gfycat(self, url: str) -> None:
        scheme, netloc, path, *_ = urlsplit(url)

        post_id, *_ = path[1:].split("-")

        async with self.bot.session.get(f"https://api.gfycat.com/v1/gfycats/{post_id}",
                                        raise_for_status=True) as response:
            data = await response.json(loads=ujson.loads)

        if data["gfyItem"]["hasAudio"]:
            self.attach_video(data["gfyItem"]["mp4Url"],
                              data["gfyItem"]["thumb100PosterUrl"],
                              data["gfyItem"]["title"] or None)

        else:
            self.attach_animation(data["gfyItem"]["gifUrl"],
                                  data["gfyItem"]["thumb100PosterUrl"],
                                  data["gfyItem"]["title"] or None)

    async def attach_from_imgur(self, url: str) -> None:
        scheme, netloc, path, *_ = urlsplit(url)

        if re.match(r"/gallery/\w+", path):
            *_, post_id = path.split("/")
            async with self.bot.session.get(f"https://api.imgur.com/3/album/{post_id}",
                                            raise_for_status=True) as response:
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

                if image["type"] == "video/mp4":
                    media.append(
                        InputMedia(media=image["mp4"],
                                   thumb=None,
                                   type=ContentType.VIDEO,
                                   caption=caption)
                    )

                elif image["type"] == "image/gif":
                    media.append(
                        InputMedia(media=image["gif"],
                                   thumb=None,
                                   type=ContentType.ANIMATION,
                                   caption=caption)
                    )

                elif image["type"] in ("image/png", "image/jpeg"):
                    media.append(
                        InputMedia(media=image["link"],
                                   thumb=None,
                                   type=ContentType.PHOTO,
                                   caption=caption)
                    )

            self.attach_album(media,
                              url,
                              data["data"]["title"] or None)

        else:
            post_id, *_ = path[1:].split(".")

            async with self.bot.session.get(f"https://api.imgur.com/3/image/{post_id}",
                                            raise_for_status=True) as response:
                data = await response.json(loads=ujson.loads)

            if data["data"]["type"] == "video/mp4":
                self.attach_video(data["data"]["mp4"],
                                  None,
                                  data["data"]["title"] or None)

            elif data["data"]["type"] == "image/gif":
                self.attach_video(data["data"]["mp4"],
                                  None,
                                  data["data"]["title"] or None)

            elif data["data"]["type"] in ("image/png", "image/jpeg"):
                self.attach_image(data["data"]["link"],
                                  None,
                                  data["data"]["title"] or None)


class RedditCommentReply(Reply):
    def __init__(self, trigger: Union[Message, InlineQuery]):
        if not isinstance(trigger, Message):
            raise ValueError

        Reply.__init__(self, trigger, None, None, "markdown")

    async def attach_from_reddit_comment(self, url):
        async with self.bot.session.get(url + ".json",
                                        raise_for_status=True) as response:
            post = await response.json(loads=ujson.loads)

        op, comments = post

        post_data = op["data"]["children"][0]["data"]
        comment_data = comments["data"]["children"][0]["data"]

        self.attach_text(comment_data["body"])
        self.set_reply_markup(generate_reddit_buttons(url, post_data, comment_data))


def generate_reddit_buttons(url: str, post_data: Dict, comment_data: Dict = None
                            ) -> InlineKeyboardMarkup:
    scheme, netloc, path, *_ = urlsplit(url)

    permalink = post_data["permalink"]
    sub = post_data["subreddit_name_prefixed"]

    if comment_data is None:
        author = "u/" + post_data["author"]

        buttons = [
            InlineKeyboardButton("Original Post", url=urlunsplit((scheme, netloc, permalink, None, None))),
            InlineKeyboardButton(sub,             url=urlunsplit((scheme, netloc, sub, None, None)))
        ]

    else:
        comment_permalink = comment_data["permalink"]
        author = "u/" + comment_data["author"]

        buttons = [
            InlineKeyboardButton("Comment",       url=urlunsplit((scheme, netloc, comment_permalink, None, None))),
            InlineKeyboardButton("Original Post", url=urlunsplit((scheme, netloc, permalink, None, None))),
            InlineKeyboardButton(sub,             url=urlunsplit((scheme, netloc, sub, None, None)))
        ]

    return InlineKeyboardMarkup().add(*buttons)


__all__ = ["APIReply", "RedditCommentReply", "MediaNotFoundError"]
