"""Side-view rendering: a floor band, then characters drawn feet-anchored and
y-sorted. Plain full-surface blit with y-sorting -- no dirty-rect bookkeeping for
v0; at a few dozen sprites in this window it is not worth the complexity. Revisit
with LayeredDirty only if profiling shows it.
"""

from __future__ import annotations

import pygame

from twitch_playground import settings
from twitch_playground.sim.platforms import Platform
from twitch_playground.sim.world import World

# Render-only palette (kept local; settings.py is owned by another track).
# Warm neutral gray: R >= G > B gives a faint yellow cast, no blue.
_GROUND_COLOR = (50, 48, 40)
_GROUND_EDGE = (108, 103, 86)


def draw(screen: pygame.Surface, world: World) -> None:
    # The backdrop layer (render/background.py) owns the base fill and is drawn
    # before this; scene.draw only lays the ground and characters on top.
    _draw_ground(screen, world.platforms)
    # back-to-front: characters lower on screen (larger feet-y) overlap those behind
    for char in sorted(world.characters.values(), key=lambda c: c.pos.y):
        cx, cy = int(char.pos.x), int(char.pos.y)
        # The sheet pose faces left (the unflipped art); flip horizontally to
        # face right. char.facing carries a WALK_THRESHOLD deadzone, so a
        # near-idle character does not flicker between flipped and unflipped.
        surf = char.surface
        if char.facing > 0:
            surf = pygame.transform.flip(surf, True, False)
        rect = surf.get_rect(midbottom=(cx, cy))  # feet anchored at pos
        screen.blit(surf, rect)
        plate_rect = char.nameplate.get_rect(midbottom=(cx, rect.top - 2))
        screen.blit(char.nameplate, plate_rect)


def _draw_ground(screen: pygame.Surface, platforms: list[Platform]) -> None:
    for p in platforms:
        if not _is_ground(p):
            continue
        # the ground fills everything from its surface down to the bottom edge
        band = pygame.Rect(0, int(p.top), settings.SCREEN_W, settings.SCREEN_H - int(p.top))
        screen.fill(_GROUND_COLOR, band)
        pygame.draw.line(screen, _GROUND_EDGE, (0, int(p.top)), (settings.SCREEN_W, int(p.top)), 2)


def _is_ground(p: Platform) -> bool:
    """Full-width platform == the floor (platform index 0 per the level contract)."""
    return p.left <= 0 and p.right >= settings.SCREEN_W
