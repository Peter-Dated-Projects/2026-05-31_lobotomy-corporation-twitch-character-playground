"""Horizontal-only steering helpers for the sidescroller. Pure functions over
vectors so they stay testable and free of any Character/pygame-sprite coupling.

Characters move along surfaces, so the only steering force is a horizontal
nudge that keeps neighbours sharing a surface from fully overlapping. Vertical
motion is gravity/jump, handled by the Character itself.
"""

from __future__ import annotations

import random as _random

from pygame.math import Vector2

from twitch_playground import settings


def steer_toward(current: float, desired: float, max_delta: float) -> float:
    """Ease a 1-D velocity toward ``desired``, capping the change to ``max_delta``.

    Reynolds steering collapsed to one axis: ``steering = desired - current``,
    clamped so the velocity changes by at most ``max_delta`` this step (i.e.
    ``MAX_FORCE * dt``). Returns the new velocity; the caller still clamps the
    magnitude to ``MAX_SPEED``. When the gap is within the cap it lands exactly
    on ``desired`` (so easing to a stop reaches a true zero, not an asymptote).
    """
    delta = desired - current
    if delta > max_delta:
        delta = max_delta
    elif delta < -max_delta:
        delta = -max_delta
    return current + delta


def wander_heading(heading: float, dt: float, rng: _random.Random = _random) -> float:
    """Drift a persistent 1-D wander heading (a signed desired speed, px/s).

    Each call nudges ``heading`` by a small random delta -- coherent over time,
    NOT a fresh reroll -- so meandering reads as intentional rather than
    coin-flip jitter. With a small per-second probability it applies a larger
    reorientation (a change of mind). The result is clamped to +/-WALK_SPEED.

    ``rng`` is injectable so tests can drive it deterministically.
    """
    heading += rng.uniform(-1.0, 1.0) * settings.WANDER_DISPLACE * dt
    if rng.random() < settings.WANDER_REORIENT_CHANCE * dt:
        heading += rng.uniform(-1.0, 1.0) * settings.WALK_SPEED
    limit = settings.WALK_SPEED
    return max(-limit, min(limit, heading))


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
