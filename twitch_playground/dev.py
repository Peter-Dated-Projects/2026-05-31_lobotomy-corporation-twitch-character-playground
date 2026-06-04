"""Keyboard-driven command injector for developing without a live Twitch chat.

It produces the exact same ChatCommand objects the Twitch thread would, onto the
same queue, so the sim cannot tell the difference between a real viewer and a
keypress. This is how we iterate on the sim with zero Twitch dependency.

Keys:
  J  a new fake viewer joins
  H  a random viewer hugs another
  F  a random viewer follows another
  L  a random viewer leaves their group
  K  fill the org to the MAX_CHARACTERS cap (so the next J shows the denial)
  `  (backquote) toggle the debug HUD overlay
"""

from __future__ import annotations

import os
import queue
import random
from typing import Callable

import pygame

from twitch_playground import settings
from twitch_playground.assets.lobcorp_renderer import LobCorpProvider
from twitch_playground.assets.provider import AssetProvider, PlaceholderProvider
from twitch_playground.chat.commands import ChatCommand

HELP = "[dev] J=join  H=hug  F=follow  L=leave  K=fill-to-cap  `=toggle HUD"


def make_provider() -> AssetProvider:
    """Pick the asset provider for this run.

    Real LobCorp art is loaded when the asset drop is present on disk; otherwise
    we fall back to procedural placeholder sprites so the app runs anywhere
    without the (un-checked-in) sheets. LobCorpProvider degrades per-character
    on its own too, so a partial/corrupt drop still won't crash the app.

    Must be called after pygame.display.set_mode() -- providers build surfaces
    with convert_alpha(), which needs an active video mode.
    """
    if os.path.isdir(settings.ASSETS_ROOT):
        return LobCorpProvider()
    print(f"[dev] LobCorp asset drop not found at {settings.ASSETS_ROOT!r}; using placeholder sprites")
    return PlaceholderProvider()


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
        elif key == pygame.K_k:
            # fill the org up to the cap so the NEXT join (a J press) is the
            # over-cap applicant that triggers the "Organization not hiring."
            # denial -- saves pressing J a hundred times. Enqueues only as many
            # joins as are needed to reach the cap from the current roster.
            needed = max(0, settings.MAX_CHARACTERS - len(self._roster()))
            for _ in range(needed):
                self._counter += 1
                self._out.put_nowait(ChatCommand("join", [], f"viewer{self._counter}"))

    def _two_distinct(self) -> tuple[str | None, str | None]:
        roster = self._roster()
        if len(roster) < 2:
            return None, None
        a, b = random.sample(roster, 2)
        return a, b
