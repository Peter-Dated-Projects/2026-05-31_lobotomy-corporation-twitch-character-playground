"""Side-view rendering: a floor band, floating platform slabs, then characters
drawn feet-anchored and y-sorted. Plain full-surface blit with y-sorting -- no
dirty-rect bookkeeping for v0; at a few dozen sprites in this window it is not
worth the complexity. Revisit with LayeredDirty only if profiling shows it.
"""

from __future__ import annotations

import pygame

from twitch_playground import settings
from twitch_playground.sim.platforms import Platform
from twitch_playground.sim.world import World

# Render-only palette (kept local; settings.py is owned by another track).
_GROUND_COLOR = (40, 44, 54)
_PLATFORM_COLOR = (58, 64, 78)
_PLATFORM_EDGE = (96, 104, 124)
_PLATFORM_THICKNESS = 12  # drawn height of a floating slab below its top edge


def draw(screen: pygame.Surface, world: World) -> None:
    screen.fill(settings.BG_COLOR)
    _draw_platforms(screen, world.platforms)
    # back-to-front: characters lower on screen (larger feet-y) overlap those behind
    for char in sorted(world.characters.values(), key=lambda c: c.pos.y):
        cx, cy = int(char.pos.x), int(char.pos.y)
        # The sheet pose faces right (facing == 1); flip horizontally to face
        # left. char.facing carries a WALK_THRESHOLD deadzone, so a near-idle
        # character does not flicker between flipped and unflipped.
        surf = char.surface
        if char.facing < 0:
            surf = pygame.transform.flip(surf, True, False)
        rect = surf.get_rect(midbottom=(cx, cy))  # feet anchored at pos
        screen.blit(surf, rect)
        plate_rect = char.nameplate.get_rect(midbottom=(cx, rect.top - 2))
        screen.blit(char.nameplate, plate_rect)


def _draw_platforms(screen: pygame.Surface, platforms: list[Platform]) -> None:
    for p in platforms:
        if _is_ground(p):
            # the ground fills everything from its surface down to the bottom edge
            band = pygame.Rect(0, int(p.top), settings.SCREEN_W, settings.SCREEN_H - int(p.top))
            screen.fill(_GROUND_COLOR, band)
            pygame.draw.line(screen, _PLATFORM_EDGE, (0, int(p.top)), (settings.SCREEN_W, int(p.top)), 2)
        else:
            slab = pygame.Rect(int(p.left), int(p.top), int(p.right - p.left), _PLATFORM_THICKNESS)
            screen.fill(_PLATFORM_COLOR, slab)
            pygame.draw.line(screen, _PLATFORM_EDGE, slab.topleft, slab.topright, 2)


def _is_ground(p: Platform) -> bool:
    """Full-width platform == the floor (platform index 0 per the level contract)."""
    return p.left <= 0 and p.right >= settings.SCREEN_W
