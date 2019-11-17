# Unreddit Telegram bot

Convenience bot for sharing reddit links into Telegram chats.

Gets the media from reddit links shared into the chat, and embeds it properly 
in the messages for your friends who are too lazy to open the browser or install the app.

Author's implementation: [@unreddit_bot](https://t.me/unreddit_bot).

#### Prerequisites

* Python 3.6+
* pipenv
* Telegram bot API token

#### Installation

```bash
pip install pipenv && \
pipenv install
```

#### Execution

**NB:** before launching, set your bot API token and desired 
request User-agent header value ([required](https://github.com/reddit-archive/reddit/wiki/API) by Reddit) in the [config](unreddit/config.json) file.

```bash
pipenv run main
```

Since this bot is designed to react to the links shared in the group chats,
and not to be explicitly queried with `/commands`, you will want to ensure that 
it has its [privacy mode](https://core.telegram.org/bots#privacy-mode) disabled
