# Unreddit Telegram bot

Convenience bot for sharing reddit links into Telegram chats.

Gets the media from reddit links shared into the chat, and embeds it properly 
in the messages for your friends who are too lazy to open the browser or install the app.

Author's implementation: [@unreddit_bot](https://t.me/unreddit_bot).

#### Prerequisites

* Python 3.9+
* pipenv
* Telegram bot API token

#### Installation

```bash
pip install pipenv && \
pipenv install
```

#### Environment configuration

| Variable           | Type   | Description                                                                                                                                                                                                                                                                           |
|--------------------|--------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| TELEGRAM_BOT_TOKEN | String | Bot's own token for interfacing with Telegram                                                                                                                                                                                                                                         |
| REDDIT_USER_AGENT  | String | `User-Agent` header value [required](https://github.com/reddit-archive/reddit/wiki/API) for API-like requests to Reddit to not get them banned                                                                                                                                        |
| IMGUR_CLIENT_ID    | String | Client Id to use for requests to Imgur (effectively mandatory for getting content from Reddit). Requires an Imgur account.<br/>Will be injected into API requests to Imgur as a part of the value of `Authorization` header.<br/>i.e. `"Authorization": "Client-ID $IMGUR_CLIENT_ID"` |


#### Execution

```bash
TELEGRAM_BOT_TOKEN="secret" REDDIT_USER_AGENT="My awesome bot" IMGUR_CLIENT_ID="also secret" pipenv run main
```

Since this bot is designed to react to the links shared in the group chats,
and not to be explicitly queried with `/commands`, you will want to ensure that 
it has its [privacy mode](https://core.telegram.org/bots#privacy-mode) disabled
