import re
from urllib.parse import urlsplit, urlunsplit


def find_urls(text: str) -> str:
    urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text
    )

    for url in urls:
        yield url


def get_path(url: str) -> str:
    return urlsplit(url).path


def repath_url(base_url: str, new_path: str) -> str:
    scheme, netloc, *_ = urlsplit(base_url)
    return f"{urlunsplit((scheme, netloc, new_path, None, None))}"
