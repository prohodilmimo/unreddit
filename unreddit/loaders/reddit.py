import re
from typing import Dict, List, Tuple, Union

from aiohttp import ClientError

from content import *
from url_utils import repath_url, get_path
from .gfycat import GFYCAT_REGEXP, GfyCatLoader
from .imgur import IMGUR_REGEXP, ImgurLoader
from .loader import ContentLoader, MediaNotFoundError

REDDIT_REGEXP = re.compile(r"reddit\.com(/(r|u|user)/\w+/|/)(comments|s)")
REDDIT_API_URL = "https://www.reddit.com"


class RedditLoader(ContentLoader):
    def is_comment_url(self, url):
        path = [part for part in get_path(url).split("/") if part]
        return len(path) == 6 or len(path) == 4

    async def load(self, url: str) -> Tuple[Content, Metadata]:
        match = REDDIT_REGEXP.search(url)

        if not match:
            raise MediaNotFoundError

        if 's' in match.groups():  # is an opaque share link
            url = await self._resolve_redirect(url)

        is_comment = self.is_comment_url(url)

        op, comments = await self._load(repath_url(REDDIT_API_URL, get_path(url)) + ".json")

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
                                  not is_comment and
                                  not is_link_to_imgur and
                                  not is_link_to_gfycat):
            raise MediaNotFoundError

        if is_video:
            return self.get_video(post_data, title, thumbnail), metadata

        elif is_gallery:
            return self.get_gallery(post_data, title), metadata

        elif post_hint == "image" or (post_hint is None and is_reddit_media):
            return self.get_image(post_data, title, thumbnail, post_hint), metadata

        elif is_link_to_imgur:
            return await self.get_imgur_content(post_data, title), metadata

        elif is_link_to_gfycat:
            return await self.get_gfycat_content(post_data, title), metadata

        # Video embeds
        elif post_hint == "rich:video":
            if is_nsfw:
                return Link(post_data["url"], title, icon="🔞"), metadata

            else:
                return Link(post_data["url"], title, icon="🎬"), metadata

        # Links
        elif post_hint == "link":
            return Link(post_data["url"], title), metadata

        elif is_comment:
            comment_data = comments["data"]["children"][0]["data"]

            metadata = RedditMetadata(url, post_data, comment_data)

            return Text(comment_data["body"], parse_mode="markdown"), metadata

        else:
            raise MediaNotFoundError

    def get_video(self, post_data, title, thumbnail):
        try:
            thumbnail = post_data["preview"]["images"][0]["resolutions"][0]["url"]
        except (IndexError, KeyError):
            pass

        if thumbnail:
            thumbnail = thumbnail.replace("&amp;", "&")

        return Video(post_data["secure_media"]["reddit_video"]["fallback_url"], thumbnail, title)

    def get_gallery(self, post_data, title) -> Album:
        media = []

        for item in post_data["gallery_data"]["items"]:
            image = post_data["media_metadata"][item["media_id"]]
            caption = None

            if image["status"] != "valid":
                continue

            if "caption" in item and item["caption"]:
                caption = item["caption"]

            if image["m"] in ("image/png", "image/jpg"):
                media.append(Image(image["s"]["u"].replace("&amp;", "&"), None, caption))

            elif image["m"] == "image/gif":
                media.append(Animation(image["s"]["u"].replace("&amp;", "&"), None, caption))

        return Album(media, post_data["url"], title)

    def get_image(self, post_data, title, thumbnail, post_hint) -> Union[Image, Animation]:
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
            return Animation(image_url, thumbnail, title)

        else:
            return Image(image_url, thumbnail, title)

    async def get_gfycat_content(self, post_data, title):
        try:
            content, _ = await GfyCatLoader(parent=self).load(post_data['url'])

            content.caption = title
            return content

        except ClientError:
            return Link(post_data["url"], title, icon="🎬")

    async def get_imgur_content(self, post_data, title):
        try:
            content, _ = await ImgurLoader(parent=self).load(post_data['url'])

            content.caption = title
            return content

        except ClientError:
            return Link(post_data["url"], title, icon="🖼")


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


__all__ = ["RedditLoader", "REDDIT_REGEXP"]
