import json
from random import randint
from typing import Dict, List
from unittest.mock import Mock, AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import Message, Chat, InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web
from aiohttp.web_request import Request
from pytest_aiohttp.plugin import aiohttp_server

MESSAGE_ID = randint(1, 1000)


@pytest.fixture
def bot(chat):
    bot = Mock(spec=Bot)
    bot.send_message = AsyncMock(side_effect=lambda **kwargs: get_message(chat))
    bot.send_photo = AsyncMock(side_effect=lambda **kwargs: get_message(chat))
    bot.send_video = AsyncMock(side_effect=lambda **kwargs: get_message(chat))
    bot.send_animation = AsyncMock(side_effect=lambda *args, **kwargs: get_message(chat))
    bot.send_media_group = AsyncMock(side_effect=lambda chat_id, media, **kwargs: [get_message(chat) for _ in media])
    return bot


@pytest.fixture
def chat():
    chat = Mock(spec=Chat)
    chat.id = randint(1, 1000)
    return chat


def get_message(chat, text=None):
    message = Message()
    global MESSAGE_ID
    message.message_id = MESSAGE_ID
    MESSAGE_ID += 1
    message.chat = chat
    if text:
        message.text = text
    return message


class InlineKeyboardMarkupMock(object):
    def __init__(self, inline_keyboard: List[List["InlineKeyboardButtonMock"]]) -> None:
        self.inline_keyboard = inline_keyboard

    def __eq__(self, other):
        if isinstance(other, InlineKeyboardMarkup):
            return all(
                self_button == other_button
                for self_row, other_row in zip(self.inline_keyboard, other.inline_keyboard)
                for self_button, other_button in zip(self_row, other_row)
            )
        elif isinstance(other, InlineKeyboardMarkupMock):
            return all(
                self_button == other_button
                for self_row, other_row in zip(self.inline_keyboard, other.inline_keyboard)
                for self_button, other_button in zip(self_row, other_row)
            )
        return False

    def __ne__(self, other):
        if isinstance(other, InlineKeyboardMarkup):
            return any(
                self_button != other_button
                for self_row, other_row in zip(self.inline_keyboard, other.inline_keyboard)
                for self_button, other_button in zip(self_row, other_row)
            )
        elif isinstance(other, InlineKeyboardMarkupMock):
            return any(
                self_button != other_button
                for self_row, other_row in zip(self.inline_keyboard, other.inline_keyboard)
                for self_button, other_button in zip(self_row, other_row)
            )
        return True

    def __repr__(self):
        return f'<InlineKeyboardMarkup mock for {self.inline_keyboard}>'


class InlineKeyboardButtonMock(object):
    def __init__(self, url, text):
        self.url = url
        self.text = text

    def __eq__(self, other):
        if isinstance(other, InlineKeyboardButton):
            return self.url == other.url and self.text == other.text
        elif isinstance(other, InlineKeyboardButtonMock):
            return self.url == other.url and self.text == other.text
        return False

    def __ne__(self, other):
        if isinstance(other, InlineKeyboardButton):
            return self.url != other.url or self.text != other.text
        elif isinstance(other, InlineKeyboardButtonMock):
            return self.url != other.url or self.text != other.text
        return True

    def __repr__(self):
        return f'<InlineKeyboardButton mock for {self.text} = {self.url}>'


def load_response(path) -> Dict:
    with open(path, "r") as file:
        return json.load(file)


@pytest.fixture
def reddit_mock_server(aiohttp_server):
    async def post_handler(request: Request):
        return web.json_response(load_response(f"reddit_responses/{request.match_info['post_hash']}.json"))

    reddit = web.Application()
    reddit.router.add_get("/r/{subreddit}/comments/{post_hash}/{title}/.json", post_handler)
    return aiohttp_server(reddit)
