from abc import abstractmethod
from typing import Tuple, Any, Dict

import ujson
from aiohttp import ClientSession

from content import Content, Metadata


class MediaNotFoundError(Exception):
    pass


class ContentLoader:
    def __init__(self, session: ClientSession = None, parent: "ContentLoader" = None):
        if session is not None:
            self.__session = session
        elif parent is not None:
            self.__session = parent.__session
        else:
            raise ValueError()

    @abstractmethod
    def get_api_url(self) -> str:
        pass

    @abstractmethod
    async def get_headers(self) -> Dict[str, str]:
        pass

    @abstractmethod
    async def load(self, url: str) -> Tuple[Content, Metadata]:
        pass

    async def _resolve_redirect(self, url: str) -> str:
        async with self.__session.head(url, headers=self.get_headers(), raise_for_status=True, allow_redirects=False) as response:
            return response.headers.get("Location")

    async def _load(self, url: str) -> Any:
        async with self.__session.get(url, headers=self.get_headers(), raise_for_status=True) as response:
            return await response.json(loads=ujson.loads)
