"""Horizontal-only steering helpers for the sidescroller. Pure functions over
vectors so they stay testable and free of any Character/pygame-sprite coupling.

Characters move along surfaces, so the only steering force is a horizontal
nudge that keeps neighbours sharing a surface from fully overlapping. Vertical
motion is gravity/jump, handled by the Character itself.
"""

from __future__ import annotations

import random as _random
from typing import NamedTuple

from pygame.math import Vector2

from twitch_playground import settings


class Neighbor(NamedTuple):
    """A lightweight per-frame snapshot of one character, built ONCE by
    ``World.update`` and shared by every steering rule (separation, cohesion,
    alignment, density) so the neighbour list is scanned once, not per rule.

    ``pos`` is a frame-start copy (so a rule never sees a neighbour move
    mid-frame); ``facing`` and ``vx`` carry heading for alignment / future
    lane logic. Later behaviour layers extend this record with emotion fields.
    """

    pos: Vector2
    facing: int
    vx: float


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


def separation_push(pos: Vector2, neighbors: list[Neighbor]) -> float:
    """Horizontal nudge (px/s, signed) away from nearby same-surface neighbours.

    Only neighbours within ``HSEP_Y_BAND`` vertically (i.e. on roughly the same
    surface) and ``HSEP_RADIUS`` horizontally contribute; the push grows as they
    get closer and is clamped to ``HSEP_PUSH``. The ``0 < dist`` test skips the
    agent's own record in the shared neighbour list.
    """
    push = 0.0
    radius = settings.HSEP_RADIUS
    for other in neighbors:
        if abs(other.pos.y - pos.y) > settings.HSEP_Y_BAND:
            continue
        dx = pos.x - other.pos.x
        dist = abs(dx)
        if 0 < dist < radius:
            push += (1.0 if dx > 0 else -1.0) * (radius - dist) / radius
    return max(-settings.HSEP_PUSH, min(settings.HSEP_PUSH, push * settings.HSEP_PUSH))


def cohesion_pull(pos: Vector2, neighbors: list[Neighbor]) -> float:
    """Horizontal nudge (px/s, signed) toward the mean x of same-surface
    neighbours within ``CROWD_COH_RADIUS`` -- pulls a straggler back toward the
    local pack. Looks further than separation. Returns 0 when nobody is in
    band/range; the magnitude grows with the offset, clamped to ``WALK_SPEED``.
    The ``0 < dist`` test skips the agent's own record.
    """
    radius = settings.CROWD_COH_RADIUS
    sum_x = 0.0
    count = 0
    for other in neighbors:
        if abs(other.pos.y - pos.y) > settings.HSEP_Y_BAND:
            continue
        if 0 < abs(other.pos.x - pos.x) <= radius:
            sum_x += other.pos.x
            count += 1
    if count == 0:
        return 0.0
    offset = sum_x / count - pos.x
    limit = settings.WALK_SPEED
    return max(-limit, min(limit, offset))


def alignment_nudge(pos: Vector2, neighbors: list[Neighbor]) -> float:
    """Horizontal nudge (px/s, signed) toward the mean velocity of same-surface
    neighbours within ``CROWD_ALI_RADIUS`` -- makes a knot of characters drift
    together instead of milling through each other. Reads the ``vx`` field of
    the shared record. Returns 0 when nobody is in band/range. The ``0 < dist``
    test skips the agent's own record.
    """
    radius = settings.CROWD_ALI_RADIUS
    sum_vx = 0.0
    count = 0
    for other in neighbors:
        if abs(other.pos.y - pos.y) > settings.HSEP_Y_BAND:
            continue
        if 0 < abs(other.pos.x - pos.x) <= radius:
            sum_vx += other.vx
            count += 1
    if count == 0:
        return 0.0
    return sum_vx / count


def local_density(pos: Vector2, neighbors: list[Neighbor]) -> int:
    """Count of same-surface neighbours within ``CROWD_DENSITY_RADIUS``.

    Free from the same shared scan; the caller uses it to slow movement in a
    crowd, gate hops when boxed in, and bias idle-pausing up. The ``0 < dist``
    test skips the agent's own record.
    """
    radius = settings.CROWD_DENSITY_RADIUS
    count = 0
    for other in neighbors:
        if abs(other.pos.y - pos.y) > settings.HSEP_Y_BAND:
            continue
        if 0 < abs(other.pos.x - pos.x) <= radius:
            count += 1
    return count
