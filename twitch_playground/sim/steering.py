"""Horizontal-only steering helpers for the sidescroller. Pure functions over
vectors so they stay testable and free of any Character/pygame-sprite coupling.

Characters move along surfaces, so the only steering force is a horizontal
nudge that keeps neighbours sharing a surface from fully overlapping. Vertical
motion is gravity/jump, handled by the Character itself.
"""

from __future__ import annotations

from pygame.math import Vector2

from twitch_playground import settings


def separation_push(pos: Vector2, neighbors: list[Vector2]) -> float:
    """Horizontal nudge (px/s, signed) away from nearby same-surface neighbours.

    Only neighbours within ``HSEP_Y_BAND`` vertically (i.e. on roughly the same
    surface) and ``HSEP_RADIUS`` horizontally contribute; the push grows as they
    get closer and is clamped to ``HSEP_PUSH``.
    """
    push = 0.0
    radius = settings.HSEP_RADIUS
    for other in neighbors:
        if abs(other.y - pos.y) > settings.HSEP_Y_BAND:
            continue
        dx = pos.x - other.x
        dist = abs(dx)
        if 0 < dist < radius:
            push += (1.0 if dx > 0 else -1.0) * (radius - dist) / radius
    return max(-settings.HSEP_PUSH, min(settings.HSEP_PUSH, push * settings.HSEP_PUSH))
