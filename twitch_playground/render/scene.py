"""Rendering: plain full-surface blit with y-sorting. No dirty-rect bookkeeping
for v0 -- at a few dozen sprites in this window it is not worth the complexity.
Revisit with LayeredDirty only if profiling shows it is needed.
"""

from __future__ import annotations

import pygame

from twitch_playground import settings
from twitch_playground.sim.world import World


def draw(screen: pygame.Surface, world: World) -> None:
    screen.fill(settings.BG_COLOR)
    # draw back-to-front so lower characters overlap those behind them
    for char in sorted(world.characters.values(), key=lambda c: c.pos.y):
        cx, cy = int(char.pos.x), int(char.pos.y)
        rect = char.surface.get_rect(center=(cx, cy))
        screen.blit(char.surface, rect)
        plate_rect = char.nameplate.get_rect(midbottom=(cx, rect.top - 2))
        screen.blit(char.nameplate, plate_rect)
