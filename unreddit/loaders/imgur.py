import re
from os import getenv
from typing import Tuple, Optional

from content import *
from url_utils import get_path
from .loader import ContentLoader

IMGUR_REGEXP = re.compile(r"imgur\.com")
IMGUR_API_URL_DEFAULT = "https://api.imgur.com"
IMGUR_API_URL_KEY = "IMGUR_API_URL"


def _from_gallery_item(image) -> Optional[Media]:
    if image["title"] and image["description"]:
        caption = f"{image['title']}\n\n{image['description']}"

    elif image["title"]:
        caption = image["title"]

    elif image["description"]:
        caption = image["description"]

    else:
        caption = None

    if image["type"] == "video/mp4":
        return Video(image["mp4"], None, caption)

    elif image["type"] == "image/gif":
        return Animation(image["gif"], None, caption)

    elif image["type"] in ("image/png", "image/jpeg"):
        return Image(image["link"], None, caption)


class ImgurLoader(ContentLoader):
    def get_api_url(self) -> str:
        return getenv(IMGUR_API_URL_KEY, IMGUR_API_URL_DEFAULT)

    def get_headers(self):
        return {"Authorization": f"Client-ID {getenv('IMGUR_CLIENT_ID')}"}

    async def load(self, url: str) -> Tuple[Content, Metadata]:
        path = get_path(url)

        if re.match(r"/gallery/\w+", path):
            *_, post_id = path.split("/")

            data = await self._load(f"{self.get_api_url()}/3/album/{post_id}")

            title = data["data"]["title"] or None
            media = []

            for image in data["data"]["images"]:
                item = _from_gallery_item(image)

                if item is not None:
                    media.append(item)

            return Album(media, url, title), ImgurMetadata()

        else:
            post_id, *_ = path[1:].split(".")

            data = await self._load(f"{self.get_api_url()}/3/image/{post_id}")

            title = data["data"]["title"] or None

            if data["data"]["type"] == "video/mp4":
                return Video(data["data"]["mp4"], None, title), ImgurMetadata()

            elif data["data"]["type"] == "image/gif":
                return Video(data["data"]["mp4"], None, title), ImgurMetadata()

            elif data["data"]["type"] in ("image/png", "image/jpeg"):
                return Image(data["data"]["link"], None, title), ImgurMetadata()


class ImgurMetadata(Metadata):
    pass


__all__ = ["IMGUR_REGEXP", "ImgurLoader"]
