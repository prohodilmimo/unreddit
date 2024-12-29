from typing import Union, List, Optional


def trim_text(text: str, limit=1024) -> str:
    if len(text) <= limit:
        return text

    try:
        return text[:(text.rindex("\n", 0, limit - 3) + 1)] + "\[…]"

    except ValueError:
        try:
            return text[:(text.rindex(". ", 0, limit - 4) + 1)] + " \[…]"

        except ValueError:
            try:
                return text[:(text.rindex(" ", 0, limit - 3) + 1)] + "\[…]"

            except ValueError:
                return text[:1019] + "\n\n\[…]"


class Content:
    @property
    def payload(self) -> Union[None, str, List["Content"]]:
        return self.__payload

    @property
    def caption(self) -> str:
        return self.__caption

    @caption.setter
    def caption(self, value: str) -> None:
        self.__caption = value

    def __init__(self, payload: Union[None, str, List["Content"]] = None,
                 caption: Optional[str] = None):
        self.__payload = payload
        self.__caption = caption


class Text(Content):
    @property
    def parse_mode(self) -> Optional[str]:
        return self.__parse_mode

    @parse_mode.setter
    def parse_mode(self, value: str) -> None:
        self.__parse_mode = value

    def __init__(self, text: Optional[str], parse_mode=None):
        if text is not None:
            text = trim_text(text)

        super().__init__(payload=text, caption=text)
        self.__parse_mode = parse_mode


class Link(Text):
    def __init__(self, content_url: str, caption: str, icon: str = "🔗"):
        super().__init__(f"<a href=\"{content_url}\">{icon}</a> {caption}")
        self.parse_mode = "html"
        self.caption = caption


class Media(Content):
    @property
    def icon(self) -> Optional[str]:
        return self.__icon

    @property
    def fallback(self) -> Optional[str]:
        return self.__fallback

    @property
    def descriptor(self) -> Optional[str]:
        return type(self).__name__.lower()

    @property
    def thumbnail(self) -> Optional[str]:
        return self.__thumbnail

    def __init__(self, icon: str,
                 payload: Union[None, str, List["Media"]] = None,
                 fallback: Optional[str] = None,
                 caption: Optional[str] = None,
                 thumbnail: Optional[str] = None):
        super().__init__(payload=payload, caption=caption)

        self.__icon = icon
        self.__fallback = fallback
        self.__thumbnail = thumbnail

    def get_embed_fallback_message(self):
        return f"<a href=\"{self.fallback}\">{self.icon} {self.caption}</a>" \
               f"\n\n" \
               f"[Telegram wasn't able to embed the {self.descriptor}]"


class Album(Media):
    def __init__(self, media: List[Media], fallback_url: str, caption: Optional[str]):
        super().__init__("🔗",
                         payload=media,
                         caption=caption,
                         fallback=fallback_url)


class Animation(Media):
    def __init__(self, content_url: str, thumbnail_url: Optional[str], caption: Optional[str]):
        super().__init__("🎬", payload=content_url,
                         fallback=content_url,
                         caption=caption,
                         thumbnail=thumbnail_url)


class Video(Media):
    def __init__(self, content_url: str, thumbnail_url: Optional[str], caption: Optional[str]):
        super().__init__("🎬", payload=content_url,
                         fallback=content_url,
                         caption=caption,
                         thumbnail=thumbnail_url)


class Image(Media):
    def __init__(self, content_url: str, thumbnail_url: Optional[str], caption: Optional[str]):
        super().__init__("🖼", payload=content_url,
                         fallback=content_url,
                         caption=caption,
                         thumbnail=thumbnail_url or content_url)
