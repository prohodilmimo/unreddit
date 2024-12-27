import json
from random import randint
from typing import Dict, List
from unittest.mock import Mock, patch, AsyncMock, ANY
from urllib.parse import unquote

import pytest
from aiogram import Bot
from aiogram.types import Message, Chat, InputMedia, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import BadRequest
from aiohttp import web, ClientSession
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from pytest_aiohttp.plugin import aiohttp_server

from unreddit.main import unreddit

MESSAGE_ID = randint(1, 1000)
SHARE_MAP = {}


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


class InputMediaMock(object):
    def __init__(self, media, caption=None):
        self.media = media
        self.caption = caption

    def __eq__(self, other):
        if isinstance(other, InputMedia):
            return self.media == other.media and self.caption == other.caption
        elif isinstance(other, InputMediaMock):
            return self.media == other.media and self.caption == other.caption
        return False

    def __ne__(self, other):
        if isinstance(other, InputMedia):
            return self.media != other.media or self.caption != other.caption
        elif isinstance(other, InputMediaMock):
            return self.media != other.media or self.caption != other.caption
        return True

    def __repr__(self):
        return f'<InputMedia mock for {self.media}>'


def load_response(path) -> Dict:
    with open(path, "r") as file:
        return json.load(file)


def resolve_share(share_hash) -> str:
    return SHARE_MAP[share_hash]


@pytest.fixture
def reddit_mock_server(aiohttp_server):
    async def post_handler(request: Request):
        return web.json_response(load_response(f"reddit_responses/{request.match_info['post_hash']}.json"))

    async def comment_handler(request: Request):
        return web.json_response(load_response(f"reddit_responses/{request.match_info['comment_hash']}.json"))

    async def redirect_handler(request: Request):
        return Response(status=302, headers={"Location": resolve_share(request.match_info['share_hash'])})

    reddit = web.Application()
    reddit.router.add_get("/r/{subreddit}/comments/{post_hash}/{title}/.json", post_handler)
    reddit.router.add_get("/r/{subreddit}/comments/{post_hash}/{title}/{comment_hash}/.json", comment_handler)
    reddit.router.add_head("/r/{subreddit}/s/{share_hash}/", redirect_handler)
    return aiohttp_server(reddit)


@pytest.fixture
def imgur_mock_server(aiohttp_server):
    async def post_handler(request: Request):
        return web.json_response(load_response(f"imgur_responses/{request.match_info['post_hash']}.json"))

    imgur = web.Application()
    imgur.router.add_get("/3/{type}/{post_hash}", post_handler)
    return aiohttp_server(imgur)


@pytest.mark.asyncio
async def test_image(reddit_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/ProperAnimalNames/comments/eakgxt/caaterpillar/"

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    caption = 'Caaterpillar'
    attachment_url = "https://preview.redd.it/x0jro2c32m441.jpg?auto=webp&s=7a26ed39ddb092ca26299ce2be0dcffd6c8800d9"
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/ProperAnimalNames", text="r/ProperAnimalNames")
    ]])

    Mock.assert_called_with(
        bot.send_photo,
        chat_id=message.chat.id,
        caption=caption,
        disable_notification=ANY,
        parse_mode=ANY,
        photo=attachment_url,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_gif(reddit_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/vexillologycirclejerk/comments/1hatfow/flag_of_sweden_but_jesus_died_of_a_bad_apple/"

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    caption = 'Flag of sweden but Jesus died of a bad apple'
    attachment_url = "https://preview.redd.it/h7n07ag96y5e1.gif?s=80759c90c117bfbb2ee5dfc3c1d986802de50a64"
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/vexillologycirclejerk", text="r/vexillologycirclejerk")
    ]])

    Mock.assert_called_with(
        bot.send_animation,
        message.chat.id,
        caption=caption,
        disable_notification=ANY,
        duration=ANY,
        width=ANY,
        height=ANY,
        thumb=ANY,
        parse_mode=ANY,
        animation=attachment_url,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_video(reddit_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/aww/comments/eafg2x/%CA%B8%E1%B5%83%CA%B7%E2%81%BF/"

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    caption = 'ʸᵃʷⁿ'
    attachment_url = "https://v.redd.it/w8qualuy4j441/DASH_720?source=fallback"
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=unquote(post_url), text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/aww", text="r/aww")
    ]])

    Mock.assert_called_with(
        bot.send_video,
        chat_id=message.chat.id,
        caption=caption,
        disable_notification=ANY,
        duration=ANY,
        width=ANY,
        height=ANY,
        parse_mode=ANY,
        video=attachment_url,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_link(reddit_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/formula1/comments/1en284q/rwanda_to_meet_f1_bosses_next_month_to_discuss/"

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    link_url = "https://www.motorsport.com/f1/news/rwanda-to-meet-f1-bosses-next-month-to-discuss-serious-grand-prix-bid/10642881/"
    text = f'<a href="{link_url}">🔗</a> Rwanda to meet F1 bosses next month to discuss “serious” Grand Prix bid'
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/formula1", text="r/formula1")
    ]])

    Mock.assert_called_with(
        bot.send_message,
        chat_id=message.chat.id,
        disable_notification=ANY,
        disable_web_page_preview=ANY,
        text=text,
        parse_mode='html',
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_gallery(reddit_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/masseffect/comments/ioubvj/for_13_year_old_game_it_sure_is_stunning_visuals/"

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    caption = 'For 13 year old game, it sure is stunning visuals...'
    attachments = [
        InputMediaMock(media="https://preview.redd.it/boq7x0gwmxl51.png?width=676&format=png&auto=webp&s=16405993dc74b5f60ed7a5b673d04098ee852789",
                       caption="Red Sun"),
        InputMediaMock(media="https://preview.redd.it/mrcuiyswmxl51.png?width=676&format=png&auto=webp&s=32c25cfc1b1422da067fab14b9fdacb7d68c69e7",
                       caption="Flat Earth"),
        InputMediaMock(media="https://preview.redd.it/0haqhd3xmxl51.png?width=676&format=png&auto=webp&s=4d8753ee504cc1b2f669b02d3b8154b24021db05",
                       caption="scars offworld")
    ]
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/masseffect", text="r/masseffect")
    ]])

    Mock.assert_called_with(
        bot.send_media_group,
        message.chat.id,
        media=attachments,
        disable_notification=ANY,
        reply_to_message_id=message.message_id
    )

    Mock.assert_called_with(
        bot.send_message,
        chat_id=message.chat.id,
        disable_notification=ANY,
        disable_web_page_preview=ANY,
        text=caption,
        parse_mode=ANY,
        reply_markup=buttons,
        reply_to_message_id=message.message_id + 1
    )


@pytest.mark.asyncio
async def test_comment(reddit_mock_server, chat, bot):
    share_url = "https://www.reddit.com/r/ShitpostXIV/s/7qTY1lb9Dc/"
    comment_url = "https://www.reddit.com/r/ShitpostXIV/comments/1hl0gyj/breaking_news_in_response_to_the_people/m3ij6ht/"
    SHARE_MAP["7qTY1lb9Dc"] = comment_url

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, share_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    post_permalink = "https://www.reddit.com/r/ShitpostXIV/comments/1hl0gyj/breaking_news_in_response_to_the_people/"
    text = "This was mildly amusing as a comment on the big post; as a standalone post it's not very good."
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=comment_url, text="Comment"),
        InlineKeyboardButtonMock(url=post_permalink, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/ShitpostXIV", text="r/ShitpostXIV")
    ]])

    Mock.assert_called_with(
        bot.send_message,
        chat_id=message.chat.id,
        disable_notification=ANY,
        disable_web_page_preview=ANY,
        text=text,
        parse_mode=ANY,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_crosspost(reddit_mock_server, chat, bot):
    share_url = "https://www.reddit.com/r/badukshitposting/s/auJDBZLHYO/"
    post_url = "https://www.reddit.com/r/badukshitposting/comments/1hbq2co/how_the_heck_am_i_supposed_to_play_this/"
    SHARE_MAP["auJDBZLHYO"] = post_url

    reddit_server = await reddit_mock_server
    async with ClientSession() as session:
        bot.session = session
        message = get_message(chat, share_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    caption = "How the heck am I supposed to play this?"
    attachment_url = "https://preview.redd.it/ps319gqzt36e1.png?auto=webp&s=ce817f1c5c0c57b2fc0b8908a378f1c0b9ab3864"
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/badukshitposting", text="r/badukshitposting")
    ]])

    Mock.assert_called_with(
        bot.send_photo,
        chat_id=message.chat.id,
        caption=caption,
        disable_notification=ANY,
        parse_mode=ANY,
        photo=attachment_url,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_imgur_video(reddit_mock_server, imgur_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/aww/comments/aie643/giving_a_fennec_fox_a_bath/"

    reddit_server = await reddit_mock_server
    imgur_server = await imgur_mock_server
    async with (ClientSession() as session):
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"), \
             patch("api_reply.APIReply.IMGUR_API_URL", f"{imgur_server.make_url('')}"):
            await unreddit(message)

    caption = 'Giving a fennec fox a bath'
    attachment_url = "https://i.imgur.com/r8v9NAI.mp4"
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/aww", text="r/aww")
    ]])

    Mock.assert_called_with(
        bot.send_video,
        chat_id=message.chat.id,
        caption=caption,
        disable_notification=ANY,
        duration=ANY,
        width=ANY,
        height=ANY,
        parse_mode=ANY,
        video=attachment_url,
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )


@pytest.mark.asyncio
async def test_imgur_gallery(reddit_mock_server, imgur_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/firebrigade/comments/dxhrr1/fire_forces_princess_hibana_wallpaper_series/"

    reddit_server = await reddit_mock_server
    imgur_server = await imgur_mock_server
    async with (ClientSession() as session):
        bot.session = session
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"), \
             patch("api_reply.APIReply.IMGUR_API_URL", f"{imgur_server.make_url('')}"):
            await unreddit(message)

    caption = "Fire Force's Princess Hibana wallpaper series [1920x1080] (stills from latest episode, mild spoilers inside)"
    attachments = [
        InputMediaMock(media="https://i.imgur.com/RVftsAw.jpg"),
        InputMediaMock(media="https://i.imgur.com/4FYXnmp.jpg"),
        InputMediaMock(media="https://i.imgur.com/m1sgnlq.jpg"),
        InputMediaMock(media="https://i.imgur.com/aAGms4f.jpg"),
        InputMediaMock(media="https://i.imgur.com/aMkM0tO.jpg"),
        InputMediaMock(media="https://i.imgur.com/OrjV12J.jpg"),
        InputMediaMock(media="https://i.imgur.com/BZJt0BH.jpg")
    ]
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/firebrigade", text="r/firebrigade")
    ]])

    Mock.assert_called_with(
        bot.send_media_group,
        message.chat.id,
        media=attachments,
        disable_notification=ANY,
        reply_to_message_id=message.message_id
    )

    Mock.assert_called_with(
        bot.send_message,
        chat_id=message.chat.id,
        disable_notification=ANY,
        disable_web_page_preview=ANY,
        text=caption,
        parse_mode=ANY,
        reply_markup=buttons,
        reply_to_message_id=message.message_id + 1
    )


@pytest.mark.asyncio
async def test_fallback(reddit_mock_server, imgur_mock_server, chat, bot):
    post_url = "https://www.reddit.com/r/Animemes/comments/e7eno4/mob_chuuni_200_op_chuunibyou_x_mob_psycho_100/"

    reddit_server = await reddit_mock_server
    async with (ClientSession() as session):
        bot.session = session
        bot.send_video = AsyncMock(side_effect=BadRequest("Mock Error"))
        message = get_message(chat, post_url)

        with patch("aiogram.types.base.TelegramObject.bot", bot), \
             patch("api_reply.APIReply.REDDIT_API_URL", f"{reddit_server.make_url('')}"):
            await unreddit(message)

    attachment_url = "https://v.redd.it/gfhrkwfbs7341/DASH_1080?source=fallback"
    text = (f'<a href="{attachment_url}">🎬 Mob Chuuni 200 OP (Chuunibyou X Mob Psycho 100)</a>\n'
            f'\n'
            f'[Telegram wasn\'t able to embed the video]')
    buttons = InlineKeyboardMarkupMock([[
        InlineKeyboardButtonMock(url=post_url, text="Original Post"),
        InlineKeyboardButtonMock(url="https://www.reddit.com/r/Animemes", text="r/Animemes")
    ]])

    Mock.assert_called_with(
        bot.send_message,
        chat_id=message.chat.id,
        disable_notification=ANY,
        disable_web_page_preview=ANY,
        text=text,
        parse_mode='html',
        reply_markup=buttons,
        reply_to_message_id=message.message_id
    )
