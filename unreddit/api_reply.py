import re
from typing import Dict, List, Tuple

from aiohttp import ClientError

from content import *
from reply import ContentLoader
from url_utils import repath_url, get_path


class MediaNotFoundError(Exception):
    pass


REDDIT_REGEXP = re.compile(r"reddit\.com(/(r|u|user)/\w+/|/)(comments|s)")
REDDIT_API_URL = "https://www.reddit.com"
IMGUR_REGEXP = re.compile(r"imgur\.com")
IMGUR_API_URL = "https://api.imgur.com"
GFYCAT_REGEXP = re.compile(r"gfycat\.com")
GFYCAT_API_URL = "https://api.gfycat.com"


class RedditLoader(ContentLoader):
    async def load(self, url: str) -> Tuple[Content, Metadata]:
        op, comments = await self._load(normalize_reddit_url(url) + ".json")

        post_data = op["data"]["children"][0]["data"]

        title = post_data.get("title", None)
        metadata = RedditMetadata(url, post_data)

        if "crosspost_parent_list" in post_data:
            post_data = post_data["crosspost_parent_list"][0]

        post_hint = post_data.get("post_hint")

        thumbnail = post_data.get("thumbnail", None)

        is_reddit_media = post_data.get("is_reddit_media_domain", False)
        is_gallery = post_data.get("gallery_data") is not None
        is_link_to_imgur = IMGUR_REGEXP.search(post_data['url']) is not None
        is_link_to_gfycat = GFYCAT_REGEXP.search(post_data['url']) is not None
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

            return Video(post_data["secure_media"]["reddit_video"]["fallback_url"], thumbnail, title), metadata

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

            return Album(media, post_data["url"], title), metadata

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
                return Animation(image_url, thumbnail, title), metadata

            else:
                return Image(image_url, thumbnail, title), metadata

        elif is_link_to_imgur:
            try:
                content, _ = await ImgurLoader(parent=self).load(post_data['url'])

                content.caption = title
                return content, metadata

            except ClientError:
                return Link(post_data["url"], title, icon="🎬"), metadata

        elif is_link_to_gfycat:
            try:
                content, _ = await GfyCatLoader(parent=self).load(post_data['url'])

                content.caption = title
                return content, metadata

            except ClientError:
                return Link(post_data["url"], title, icon="🖼"), metadata

        # Video embeds
        elif post_hint == "rich:video":
            if is_nsfw:
                return Link(post_data["url"], title, icon="🔞"), metadata

            else:
                return Link(post_data["url"], title, icon="🎬"), metadata

        # Links
        elif post_hint == "link":
            return Link(post_data["url"], title), metadata

        else:
            raise MediaNotFoundError


class GfyCatLoader(ContentLoader):
    async def load(self, url: str) -> Tuple[Content, Metadata]:
        path = get_path(url)

        post_id, *_ = path[1:].split("-")

        data = await self._load(f"{GFYCAT_API_URL}/v1/gfycats/{post_id}")

        if data["gfyItem"]["hasAudio"]:
            return Video(data["gfyItem"]["mp4Url"],
                         data["gfyItem"]["thumb100PosterUrl"],
                         data["gfyItem"]["title"] or None), \
                Metadata()
        else:
            return Animation(data["gfyItem"]["gifUrl"],
                             data["gfyItem"]["thumb100PosterUrl"],
                             data["gfyItem"]["title"] or None), \
                Metadata()


class ImgurLoader(ContentLoader):
    async def load(self, url: str) -> Tuple[Content, Metadata]:
        path = get_path(url)

        if re.match(r"/gallery/\w+", path):
            *_, post_id = path.split("/")
            data = await self._load(f"{IMGUR_API_URL}/3/album/{post_id}")

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

            return Album(media, url, data["data"]["title"] or None), Metadata()

        else:
            post_id, *_ = path[1:].split(".")

            data = await self._load(f"{IMGUR_API_URL}/3/image/{post_id}")

            if data["data"]["type"] == "video/mp4":
                return Video(data["data"]["mp4"], None, data["data"]["title"] or None), Metadata()

            elif data["data"]["type"] == "image/gif":
                return Video(data["data"]["mp4"], None, data["data"]["title"] or None), Metadata()

            elif data["data"]["type"] in ("image/png", "image/jpeg"):
                return Image(data["data"]["link"], None, data["data"]["title"] or None), Metadata()


class RedditCommentLoader(ContentLoader):
    async def load(self, url: str) -> Tuple[Content, Metadata]:
        op, comments = await self._load(normalize_reddit_url(url) + ".json")

        post_data = op["data"]["children"][0]["data"]
        comment_data = comments["data"]["children"][0]["data"]

        metadata = RedditMetadata(url, post_data, comment_data)
        return Text(comment_data["body"], parse_mode="markdown"), metadata


def normalize_reddit_url(url: str) -> str:
    return repath_url(REDDIT_API_URL, get_path(url))


class RedditMetadata(Metadata):
    comment_permalink = None

    def __init__(self, url: str, post_data: Dict, comment_data: Dict = None):
        self.post_permalink = repath_url(url, post_data["permalink"])
        self.sub = post_data["subreddit_name_prefixed"]
        self.sub_link = repath_url(url, self.sub)
        self.author = "u/" + post_data["author"]
        if comment_data:
            self.author = "u/" + comment_data["author"]
            self.comment_permalink = repath_url(url, comment_data["permalink"])

    def get_buttons(self) -> List[Button]:
        buttons = []

        if self.comment_permalink:
            buttons.append(Button("Comment", url=self.comment_permalink))

        buttons += [
            Button("Original Post", url=self.post_permalink),
            Button(self.sub, url=self.sub_link)
        ]

        return buttons


__all__ = ["RedditLoader", "RedditCommentLoader", "REDDIT_REGEXP", "MediaNotFoundError", "normalize_reddit_url"]
