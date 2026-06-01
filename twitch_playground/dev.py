"""Keyboard-driven command injector for developing without a live Twitch chat.

It produces the exact same ChatCommand objects the Twitch thread would, onto the
same queue, so the sim cannot tell the difference between a real viewer and a
keypress. This is how we iterate on the sim with zero Twitch dependency.

Keys:
  J  a new fake viewer joins
  H  a random viewer hugs another
  F  a random viewer follows another
  L  a random viewer leaves their group
  `  (backquote) toggle the debug HUD overlay
"""

from __future__ import annotations

import queue
import random
from typing import Callable

import pygame

from twitch_playground.chat.commands import ChatCommand

HELP = "[dev] J=join  H=hug  F=follow  L=leave  `=toggle HUD"


class DevInjector:
    def __init__(self, out: "queue.Queue[ChatCommand]", roster: Callable[[], list[str]]) -> None:
        self._out = out
        self._roster = roster  # returns current usernames in the world
        self._counter = 0

    def handle_key(self, key: int) -> None:
        if key == pygame.K_j:
            self._counter += 1
            self._out.put_nowait(ChatCommand("join", [], f"viewer{self._counter}"))
        elif key == pygame.K_h:
            a, b = self._two_distinct()
            if a and b:
                self._out.put_nowait(ChatCommand("hug", [b], a))
        elif key == pygame.K_f:
            a, b = self._two_distinct()
            if a and b:
                self._out.put_nowait(ChatCommand("follow", [b], a))
        elif key == pygame.K_l:
            roster = self._roster()
            if roster:
                self._out.put_nowait(ChatCommand("leave", [], random.choice(roster)))

    def _two_distinct(self) -> tuple[str | None, str | None]:
        roster = self._roster()
        if len(roster) < 2:
            return None, None
        a, b = random.sample(roster, 2)
        return a, b
