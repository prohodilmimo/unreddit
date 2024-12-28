import re
from typing import Dict, List

from aiohttp import ClientError

from content import *
from reply import Reply
from url_utils import repath_url, get_path


class MediaNotFoundError(Exception):
    pass


class APIReply(Reply):
    REDDIT_REGEXP = re.compile(r"reddit\.com(/(r|u|user)/\w+/|/)(comments|s)")
    REDDIT_API_URL = "https://www.reddit.com"
    IMGUR_REGEXP = re.compile(r"imgur\.com")
    IMGUR_API_URL = "https://api.imgur.com"
    GFYCAT_REGEXP = re.compile(r"gfycat\.com")
    GFYCAT_API_URL = "https://api.gfycat.com"

    async def attach_from_reddit(self, url: str) -> None:
        op, comments = await self.load(normalize_reddit_url(url) + ".json")

        post_data = op["data"]["children"][0]["data"]

        title = post_data.get("title", None)
        self.set_reply_markup(generate_reddit_buttons(url, post_data))

        if "crosspost_parent_list" in post_data:
            post_data = post_data["crosspost_parent_list"][0]

        post_hint = post_data.get("post_hint")

        thumbnail = post_data.get("thumbnail", None)

        is_reddit_media = post_data.get("is_reddit_media_domain", False)
        is_gallery = post_data.get("gallery_data") is not None
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

            self.attach_content(Video(post_data["secure_media"]["reddit_video"]["fallback_url"],
                                      thumbnail,
                                      title))

        elif is_gallery:
            media = []

            for item in post_data["gallery_data"]["items"]:
                image = post_data["media_metadata"][item["media_id"]]
                caption = None

                if image["status"] != "valid":
                    continue

                if item["caption"]:
                    caption = item["caption"]

                if image["m"] in ("image/png", "image/jpg"):
                    media.append(Image(image["s"]["u"].replace("&amp;", "&"), None, caption))

                elif image["m"] == "image/gif":
                    media.append(Animation(image["s"]["u"].replace("&amp;", "&"), None, caption))

            self.attach_content(Album(media, post_data["url"], title))

        elif post_hint == "image" or (post_hint is None and is_reddit_media):
            image_url = post_data["url"]

            is_gif = re.search(r"\.gif", image_url, re.I)

            if post_hint is not None and is_gif:
                image_url = post_data["preview"]["images"][0]["variants"]["gif"]["source"]["url"]

            elif post_hint is not None:
                image_url = post_data["preview"]["images"][0]["source"]["url"]
                try:
                    thumbnail = post_data["preview"]["images"][0]["resolutions"][0]["url"]
                except (IndexError, KeyError):
                    pass

            image_url = image_url.replace("&amp;", "&")

            if thumbnail:
                thumbnail = thumbnail.replace("&amp;", "&")

            if is_gif:
                self.attach_content(Animation(image_url, thumbnail, title))

            else:
                self.attach_content(Image(image_url, thumbnail, title))

        elif is_link_to_imgur:
            try:
                await self.attach_from_imgur(post_data['url'])

                self.set_caption(title)

            except ClientError:
                self.attach_content(Link(post_data["url"], title, icon="🖼"))

        elif is_link_to_gfycat:
            try:
                await self.attach_from_gfycat(post_data['url'])

                self.set_caption(title)

            except ClientError:
                self.attach_content(Link(post_data["url"], title, icon="🎬"))

        # Video embeds
        elif post_hint == "rich:video":
            if is_nsfw:
                self.attach_content(Link(post_data["url"], title, icon="🔞"))

            else:
                self.attach_content(Link(post_data["url"], title, icon="🎬"))

        # Links
        elif post_hint == "link":
            self.attach_content(Link(post_data["url"], title))

        else:
            raise MediaNotFoundError

    async def attach_from_gfycat(self, url: str) -> None:
        path = get_path(url)

        post_id, *_ = path[1:].split("-")

        data = await self.load(f"{self.GFYCAT_API_URL}/v1/gfycats/{post_id}")

        if data["gfyItem"]["hasAudio"]:
            self.attach_content(Video(data["gfyItem"]["mp4Url"],
                                      data["gfyItem"]["thumb100PosterUrl"],
                                      data["gfyItem"]["title"] or None))

        else:
            self.attach_content(Animation(data["gfyItem"]["gifUrl"],
                                          data["gfyItem"]["thumb100PosterUrl"],
                                          data["gfyItem"]["title"] or None))

    async def attach_from_imgur(self, url: str) -> None:
        path = get_path(url)

        if re.match(r"/gallery/\w+", path):
            *_, post_id = path.split("/")
            data = await self.load(f"{self.IMGUR_API_URL}/3/album/{post_id}")

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
                    media.append(Video(image["mp4"], None, caption))

                elif image["type"] == "image/gif":
                    media.append(Animation(image["gif"], None, caption))

                elif image["type"] in ("image/png", "image/jpeg"):
                    media.append(Image(image["link"], None, caption))

            self.attach_content(Album(media, url, data["data"]["title"] or None))

        else:
            post_id, *_ = path[1:].split(".")

            data = await self.load(f"{self.IMGUR_API_URL}/3/image/{post_id}")

            if data["data"]["type"] == "video/mp4":
                self.attach_content(Video(data["data"]["mp4"], None, data["data"]["title"] or None))

            elif data["data"]["type"] == "image/gif":
                self.attach_content(Video(data["data"]["mp4"], None, data["data"]["title"] or None))

            elif data["data"]["type"] in ("image/png", "image/jpeg"):
                self.attach_content(Image(data["data"]["link"], None, data["data"]["title"] or None))


class RedditCommentReply(Reply):
    async def attach_from_reddit_comment(self, url):
        op, comments = await self.load(normalize_reddit_url(url) + ".json")

        post_data = op["data"]["children"][0]["data"]
        comment_data = comments["data"]["children"][0]["data"]

        self.attach_content(Text(comment_data["body"], "markdown"))
        self.set_reply_markup(generate_reddit_buttons(url, post_data, comment_data))


def normalize_reddit_url(url: str) -> str:
    return repath_url(APIReply.REDDIT_API_URL, get_path(url))


def generate_reddit_buttons(url: str, post_data: Dict, comment_data: Dict = None
                            ) -> List[Button]:
    permalink = post_data["permalink"]
    sub = post_data["subreddit_name_prefixed"]
    author = "u/" + post_data["author"]

    buttons = []

    if comment_data is not None:
        author = "u/" + comment_data["author"]
        comment_permalink = comment_data["permalink"]

        buttons.append(Button("Comment", url=repath_url(url, comment_permalink)))

    buttons += [
        Button("Original Post", url=repath_url(url, permalink)),
        Button(sub, url=repath_url(url, sub))
    ]

    return buttons


__all__ = ["APIReply", "RedditCommentReply", "MediaNotFoundError", "normalize_reddit_url"]
