# Twitch Chat Integration Research

Research brief for connecting a Python/pygame application to Twitch chat to listen for viewer commands.

---

## Recommended Approach

**Use `twitchio` with a background thread and a `queue.Queue` to pass command events to the pygame main loop.**

twitchio is the clear winner for this use case: it handles IRC authentication, reconnection, rate limits, and message parsing out of the box. Raw IRC is not worth the maintenance burden here, and EventSub is overkill for a local toy/playground app. The thread-safe queue keeps pygame's render loop clean.

---

## Twitch IRC Protocol

Twitch chat is served over IRC (Internet Relay Chat) on `irc.chat.twitch.tv`, port 6667 (plain) or 6697 (TLS). The flow is:

1. Open a TCP socket to the server.
2. Send `PASS oauth:<token>` and `NICK <bot_username>`.
3. Request capability tags: `CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership` — these add extra metadata to messages (badges, emotes, user ID, etc.).
4. Send `JOIN #<channel_name>` to subscribe to a channel's chat.
5. Listen for `PRIVMSG` events. When the server sends `PING :tmi.twitch.tv`, respond with `PONG :tmi.twitch.tv` or the connection drops after ~5 minutes.

Authentication uses an OAuth bearer token scoped to a Twitch account. The username must match the account that owns the token. Twitch's IRC endpoint is a wrapper over their internal system — it is stable but the protocol quirks (custom `@tags` prefix, `USERSTATE`, `GLOBALUSERSTATE`, `RECONNECT`) require custom parsing if you go raw.

---

## Library Comparison: twitchio vs Raw IRC vs WebSocket

### twitchio

- Pure Python async library built on `asyncio` and `aiohttp`.
- Handles authentication, `PING`/`PONG`, reconnection, capability negotiation automatically.
- Clean event model: subclass `twitchio.Client`, define `event_message(msg)`.
- Parses the `@tags` metadata for you (author, badges, emotes, etc.).
- Rate limits are respected internally.
- **Drawback**: asyncio-based, so running it alongside a synchronous pygame loop requires a thread or `asyncio.run_coroutine_threadsafe`.
- Actively maintained; version 2.x is current (as of 2025).

### Raw IRC socket

- Full control, zero dependencies.
- You must implement: `PING`/`PONG`, reconnection logic, tag parsing, capability negotiation.
- `@tags` parsing is fiddly — the `@key=value;key=value` prefix is Twitch-specific and not standard IRC.
- Worth it only if you want minimal deps or are embedding in an environment where twitchio can't be installed.

### WebSocket (`wss://irc-ws.chat.twitch.tv:443`)

- Same IRC protocol over WebSocket instead of raw TCP. Twitch offers this for browser clients, but there is no advantage in a Python context — you still speak the same IRC dialect, just wrapped in websocket frames.
- `websockets` library adds another dep for no gain over plain sockets.
- Not recommended.

### EventSub (HTTP webhook / WebSocket)

- Twitch's modern eventing system. Can subscribe to `channel.chat.message` events.
- Requires a public HTTPS endpoint (webhook mode) or a persistent WebSocket (WebSocket mode added in 2023).
- Strongly typed JSON payloads, no IRC parsing needed.
- **Overkill for a local app**: WebSocket EventSub still requires registering an app on the Twitch developer console and handling subscription lifecycle. No simpler than twitchio in practice.
- Worth considering if you later need server-side deployment or multiple event types (follows, subs, channel points) from one connection.

**Decision**: twitchio for this project.

---

## Command Prefix Parsing

Twitch chat messages arrive as `twitchio.Message` objects. The content is in `msg.content`. A simple prefix check:

```python
def parse_command(content: str) -> tuple[str, list[str]] | None:
    """Return (command, args) or None if not a command."""
    content = content.strip()
    if not content.startswith("!"):
        return None
    parts = content[1:].split()
    if not parts:
        return None
    return parts[0].lower(), parts[1:]
```

Commands like `!spawn agent`, `!character EmeraldCity` parse to `("spawn", ["agent"])` and `("character", ["emeraldcity"])`. Lowercasing the command name makes matching case-insensitive.

Filter by broadcaster/mod if you want restricted commands:

```python
if msg.author.is_mod or msg.author.name == channel_name:
    # allow privileged commands
```

---

## Rate Limits

Twitch IRC has two rate limit tiers:

| Account type | Messages per 30 seconds |
|---|---|
| Normal user | 20 |
| Verified bot / moderator in channel | 100 |

For a read-only listener that never sends chat messages, rate limits are irrelevant. If the bot needs to respond in chat (e.g., echo confirmations), stay well under 20/30s to be safe. twitchio does not auto-throttle outgoing messages — implement a token bucket if the bot talks a lot.

**Reconnection**: twitchio reconnects automatically on socket drop. The `event_error` hook fires on unhandled exceptions; add logging there. For raw IRC, implement exponential backoff: 1s, 2s, 4s, 8s, cap at 60s.

---

## Background Thread + Thread-Safe Queue (pygame integration)

pygame's render loop is synchronous and single-threaded. twitchio is asyncio-based. The pattern:

1. Create a `queue.Queue` (thread-safe).
2. Run twitchio's asyncio event loop on a daemon thread.
3. In `event_message`, parse commands and put events onto the queue.
4. In pygame's main loop, drain the queue each frame.

```python
import threading
import queue
import asyncio
import twitchio

command_queue: queue.Queue = queue.Queue()

class ChatBot(twitchio.Client):
    async def event_message(self, msg: twitchio.Message) -> None:
        if msg.echo:
            return
        result = parse_command(msg.content)
        if result:
            cmd, args = result
            command_queue.put_nowait({"cmd": cmd, "args": args, "author": msg.author.name})

    async def event_ready(self) -> None:
        print(f"Bot connected as {self.nick}")

def run_bot(token: str, channel: str) -> None:
    bot = ChatBot(token=token, initial_channels=[channel])
    bot.run()  # blocks — runs asyncio loop internally

def start_chat_thread(token: str, channel: str) -> threading.Thread:
    t = threading.Thread(target=run_bot, args=(token, channel), daemon=True)
    t.start()
    return t
```

In the pygame main loop:

```python
while running:
    # drain chat commands each frame
    while not command_queue.empty():
        event = command_queue.get_nowait()
        handle_chat_command(event)

    # ... rest of pygame loop
```

`queue.Queue` is fully thread-safe: `put_nowait` from the IRC thread and `get_nowait` from the main thread do not need additional locks. `daemon=True` means the thread dies automatically when the main process exits.

---

## OAuth Scopes and Getting a Bot Token

### Required scopes

For a **read-only chat listener**:
- `chat:read` — receive chat messages

If the bot needs to **send messages**:
- `chat:read` + `chat:edit`

That is the minimum. No other scopes needed for basic command parsing.

### Getting a token cheaply

The easiest path for a personal/playground project:

1. Go to [https://twitchtokengenerator.com](https://twitchtokengenerator.com) — a community tool that handles the OAuth flow for you. Select `chat:read` (and `chat:edit` if needed), authorize with your bot account, and copy the access token.

2. Alternatively, register a free app at [https://dev.twitch.tv/console/apps](https://dev.twitch.tv/console/apps) and run the OAuth Authorization Code flow yourself. The redirect URI can be `http://localhost:3000` for local use.

3. Store the token in a `.env` file (`TWITCH_TOKEN=oauth:xxxxx`, `TWITCH_CHANNEL=yourchannel`), never hardcode it.

Tokens expire. For a long-lived bot, implement refresh token rotation (twitchio 2.x supports this with the `AuthenticationError` event). For a short-lived playground app, manually regenerating the token periodically is fine.

---

## Minimal Working Bot Skeleton

```python
"""
twitch_chat.py — minimal Twitch chat command listener for pygame integration.

Usage:
    Set TWITCH_TOKEN and TWITCH_CHANNEL in a .env file.
    Call start_chat_thread() before your pygame loop.
    Drain command_queue each frame.
"""

import os
import queue
import threading
from dataclasses import dataclass

import twitchio
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ChatCommand:
    cmd: str
    args: list[str]
    author: str

command_queue: queue.Queue[ChatCommand] = queue.Queue()


def parse_command(content: str) -> ChatCommand | None:
    content = content.strip()
    if not content.startswith("!"):
        return None
    parts = content[1:].split()
    if not parts:
        return None
    return ChatCommand(cmd=parts[0].lower(), args=parts[1:], author="")


class ChatBot(twitchio.Client):
    async def event_ready(self) -> None:
        print(f"[twitch] connected as {self.nick}")

    async def event_message(self, msg: twitchio.Message) -> None:
        if msg.echo:
            return
        cmd = parse_command(msg.content)
        if cmd:
            cmd.author = msg.author.name
            command_queue.put_nowait(cmd)

    async def event_error(self, error: Exception, data: str | None = None) -> None:
        print(f"[twitch] error: {error}")


def _run_bot(token: str, channel: str) -> None:
    bot = ChatBot(token=token, initial_channels=[channel])
    bot.run()


def start_chat_thread() -> threading.Thread:
    token = os.environ["TWITCH_TOKEN"]
    channel = os.environ["TWITCH_CHANNEL"]
    t = threading.Thread(target=_run_bot, args=(token, channel), daemon=True)
    t.start()
    return t


# --- pygame integration example ---
#
# def main():
#     start_chat_thread()
#     pygame.init()
#     screen = pygame.display.set_mode((800, 600))
#     clock = pygame.time.Clock()
#     running = True
#     while running:
#         for event in pygame.event.get():
#             if event.type == pygame.QUIT:
#                 running = False
#         while not command_queue.empty():
#             cmd = command_queue.get_nowait()
#             if cmd.cmd == "spawn":
#                 spawn_character(cmd.args, cmd.author)
#             elif cmd.cmd == "character":
#                 set_character(cmd.args, cmd.author)
#         screen.fill((0, 0, 0))
#         pygame.display.flip()
#         clock.tick(60)
```

### Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    "twitchio>=2.10",
    "python-dotenv>=1.0",
]
```

### .env

```
TWITCH_TOKEN=oauth:your_access_token_here
TWITCH_CHANNEL=your_channel_name_here
```

---

## Summary Table

| Concern | Decision |
|---|---|
| Library | twitchio 2.x |
| Threading | daemon thread + `queue.Queue` |
| Auth | OAuth user token, scopes: `chat:read` |
| Token source | twitchtokengenerator.com or manual OAuth flow |
| Command prefix | `!` prefix, case-insensitive |
| Rate limits | irrelevant for read-only; stay under 20/30s if bot responds |
| Reconnection | automatic via twitchio |
| EventSub | skip for local/playground use; revisit if deploying server-side |
