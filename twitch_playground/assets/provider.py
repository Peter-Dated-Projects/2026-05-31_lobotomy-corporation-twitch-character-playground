"""Asset abstraction. The rest of the codebase only ever sees a SpriteSet, so
swapping placeholder art for real LobCorp DragonBones frames later touches
nothing outside this module.

NOTE: providers build surfaces with convert_alpha(), so they must be
instantiated AFTER pygame.display.set_mode().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pygame

from twitch_playground import settings


@dataclass
class SpriteSet:
    """Animation frames for one character type, keyed by clip name.

    Required clips: "idle", "walk", "jump", "hug".

    ``frames`` holds the resting "default"-emotion clips. ``emotion_frames`` is an
    optional second index ``emotion_frames[emotion][clip]`` carrying the L5 face
    variants ("default"/"battle"/"panic"); a provider that pre-renders all three
    fills it. When it is empty (or a requested emotion key is missing) ``clip``
    falls back to ``frames``, so a placeholder SpriteSet built with default art
    only still serves every emotion -- the graceful-fallback contract.
    """

    frames: dict[str, list[pygame.Surface]]
    emotion_frames: dict[str, dict[str, list[pygame.Surface]]] = field(
        default_factory=dict
    )

    def clip(self, name: str, emotion: str = "default") -> list[pygame.Surface]:
        variants = self.emotion_frames.get(emotion)
        src = variants if variants is not None else self.frames
        return src.get(name) or src["idle"]


class AssetProvider(Protocol):
    def get_sprite_set(self, character_id: str) -> SpriteSet: ...


def _body(width: int, height: int, color: tuple[int, int, int]) -> pygame.Surface:
    """Draw one placeholder body frame: a rounded capsule with a facing dot."""
    w, h = settings.SPRITE_W, settings.SPRITE_H
    surf = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
    # shadow
    pygame.draw.ellipse(surf, (0, 0, 0, 90), (w // 2 - 11, h - 8, 22, 7))
    # body capsule, centered, sized by the frame's width/height for squash/stretch
    x = (w - width) // 2
    y = h - height - 6
    pygame.draw.rect(surf, color, (x, y, width, height), border_radius=width // 2)
    # facing indicator (a light dot near the top)
    pygame.draw.circle(surf, (250, 250, 250), (w // 2 + 3, y + height // 4), 3)
    return surf


def _tint(seed: str) -> tuple[int, int, int]:
    """A single shared placeholder color for v0 (one character type)."""
    return (120, 150, 210)


class PlaceholderProvider:
    """Procedural stand-in sprites. One character type; identity comes from the
    nameplate, not the art."""

    def __init__(self) -> None:
        self._cache: dict[str, SpriteSet] = {}

    def get_sprite_set(self, character_id: str) -> SpriteSet:
        if character_id not in self._cache:
            self._cache[character_id] = self._build(_tint(character_id))
        return self._cache[character_id]

    def _build(self, color: tuple[int, int, int]) -> SpriteSet:
        bw, bh = 18, 26  # nominal body size
        # idle: gentle vertical breathing via a 1px height bob
        idle = [_body(bw, bh, color), _body(bw, bh + 1, color)]
        # walk: squash/stretch cycle so motion reads at low fps
        walk = [
            _body(bw, bh, color),
            _body(bw + 2, bh - 2, color),
            _body(bw, bh, color),
            _body(bw - 2, bh + 2, color),
        ]
        # jump: a stretched airborne pose -- narrower and taller, held as a
        # near-static clip while the character is off the ground.
        jump = [
            _body(bw - 3, bh + 6, color),
            _body(bw - 4, bh + 8, color),
        ]
        # hug: widen arms outward then back (placeholder for a real hug clip)
        hug = [
            _body(bw, bh, color),
            _body(bw + 5, bh - 1, color),
            _body(bw + 8, bh - 2, color),
            _body(bw + 5, bh - 1, color),
        ]
        return SpriteSet({"idle": idle, "walk": walk, "jump": jump, "hug": hug})
