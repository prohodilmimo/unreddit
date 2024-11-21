import re
from typing import Tuple

from content import Metadata, Content, Animation, Video
from url_utils import get_path
from .loader import ContentLoader

GFYCAT_REGEXP = re.compile(r"gfycat\.com")
GFYCAT_API_URL = "https://api.gfycat.com"


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


__all__ = ["GFYCAT_REGEXP", "GfyCatLoader"]
