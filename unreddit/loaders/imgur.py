import re
from typing import Tuple

from content import *
from url_utils import get_path
from .loader import ContentLoader

IMGUR_REGEXP = re.compile(r"imgur\.com")
IMGUR_API_URL = "https://api.imgur.com"


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


__all__ = ["IMGUR_REGEXP", "ImgurLoader"]
