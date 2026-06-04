"""Twitch IRC listener. Runs twitchio on a daemon thread and pushes parsed
ChatCommands onto a shared queue. Knows nothing about rendering or the sim.
"""

from __future__ import annotations

import asyncio
import os
import queue
import threading

import twitchio

from twitch_playground.chat import auth
from twitch_playground.chat.commands import ChatCommand, parse_command


class _ChatBot(twitchio.Client):
    def __init__(self, token: str, channel: str, out: "queue.Queue[ChatCommand]") -> None:
        super().__init__(token=token, initial_channels=[channel])
        self._out = out

    async def event_ready(self) -> None:
        print(f"[twitch] connected as {self.nick}")

    async def event_message(self, message: twitchio.Message) -> None:
        if message.echo:
            return
        author = message.author.name if message.author else ""
        cmd = parse_command(message.content, author)
        if cmd:
            self._out.put_nowait(cmd)

    async def event_error(self, error: Exception, data: str | None = None) -> None:
        print(f"[twitch] error: {error}")


def start_chat_thread(out: "queue.Queue[ChatCommand]") -> threading.Thread | None:
    """Start the Twitch listener if credentials are configured, else return None
    (dev mode -- the keyboard injector is the only command source).

    The access token is validated (and refreshed via the refresh token if it has
    expired) before we connect -- see ``auth.ensure_access_token``."""
    token = auth.ensure_access_token()
    channel = os.environ.get("TWITCH_CHANNEL")
    if not token or not channel:
        return None

    def _run() -> None:
        # twitchio.Client.__init__ calls asyncio.get_event_loop(), which on
        # Python 3.10 only auto-creates a loop on the main thread. We run on a
        # daemon thread, so give this thread its own loop before constructing
        # the client (else: "There is no current event loop in thread ...").
        asyncio.set_event_loop(asyncio.new_event_loop())
        _ChatBot(token=token, channel=channel, out=out).run()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
