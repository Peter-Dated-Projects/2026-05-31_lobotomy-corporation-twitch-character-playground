"""Wandering steering helpers. Pure functions over vectors so they stay
testable and free of any Character/pygame-sprite coupling.

All forces are expressed per-second; the caller integrates with delta-time.
"""

from __future__ import annotations

import math
import random

from pygame.math import Vector2

from twitch_playground import settings


def wander_force(velocity: Vector2, wander_angle: float, dt: float) -> tuple[Vector2, float]:
    """Smooth, life-like direction drift. Returns (steer_force, new_wander_angle)."""
    wander_angle += random.uniform(-1.0, 1.0) * settings.WANDER_JITTER_DEG * dt
    heading = velocity.normalize() if velocity.length_squared() > 1e-6 else Vector2(1, 0)
    rad = math.radians(wander_angle)
    offset = Vector2(math.cos(rad), math.sin(rad)) * 25.0
    target_dir = heading * 60.0 + offset
    if target_dir.length_squared() < 1e-6:
        return Vector2(0, 0), wander_angle
    desired = target_dir.normalize() * settings.MAX_SPEED
    return desired - velocity, wander_angle


def separation_force(pos: Vector2, neighbors: list[Vector2]) -> Vector2:
    """Repulsion from nearby neighbors, inverse-distance weighted."""
    force = Vector2(0, 0)
    radius = settings.SEPARATION_RADIUS
    for other in neighbors:
        diff = pos - other
        dist = diff.length()
        if 0 < dist < radius:
            force += diff.normalize() / dist
    return force * settings.SEPARATION_WEIGHT


def clamp_to_bounds(pos: Vector2, velocity: Vector2, width: int, height: int) -> None:
    """Reflect velocity at the scene walls. Mutates pos and velocity in place."""
    m = settings.WALL_MARGIN
    if pos.x < m:
        pos.x = m
        velocity.x = abs(velocity.x)
    elif pos.x > width - m:
        pos.x = width - m
        velocity.x = -abs(velocity.x)
    if pos.y < m:
        pos.y = m
        velocity.y = abs(velocity.y)
    elif pos.y > height - m:
        pos.y = height - m
        velocity.y = -abs(velocity.y)
