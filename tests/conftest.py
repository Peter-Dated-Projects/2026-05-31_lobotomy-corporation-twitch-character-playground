"""Headless test harness for the sidescroller sim.

Everything here runs without a real window: we force SDL's dummy video/audio
drivers BEFORE pygame is imported, then stand up an off-screen display surface
so the asset provider's ``convert_alpha()`` calls have a video mode to bind to
(see assets/provider.py -- providers must be built after set_mode()).
"""

from __future__ import annotations

import os

# Must be set before pygame imports its video backend.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import PlaceholderProvider
from twitch_playground.sim.character import Character


@pytest.fixture(scope="session", autouse=True)
def _display():
    """A single off-screen display for the whole session.

    convert_alpha() needs an active video mode; a 64x64 dummy surface is plenty
    since nothing is ever shown."""
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.display.quit()


@pytest.fixture
def provider() -> PlaceholderProvider:
    return PlaceholderProvider()


@pytest.fixture
def sprites(provider: PlaceholderProvider):
    return provider.get_sprite_set("default")


@pytest.fixture
def calm(monkeypatch):
    """Silence the random wander decisions so physics/clip tests are deterministic.

    With both chances at 0 a grounded character neither hops nor takes idle
    pauses -- it just strolls -- so a test can assert exact grounded state."""
    monkeypatch.setattr(settings, "JUMP_CHANCE", 0.0)
    monkeypatch.setattr(settings, "IDLE_CHANCE", 0.0)


@pytest.fixture
def make_char(sprites):
    """Factory for a Character placed with its feet exactly on a y (defaults to
    the ground top so the first update() binds it to the ground platform)."""

    def _make(x: float = 50.0, y: float | None = None, username: str = "a") -> Character:
        feet_y = settings.GROUND_TOP if y is None else y
        nameplate = pygame.Surface((10, 6), pygame.SRCALPHA)
        return Character(username, (x, feet_y), sprites, nameplate)

    return _make
