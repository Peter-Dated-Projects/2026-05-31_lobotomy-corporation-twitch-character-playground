"""A single on-screen character bound to a Twitch username, living in a
sidescroller world: it strolls along surfaces, hops between platform tiers with
real gravity, and lands on one-way platforms.

Two orthogonal axes of state:
  - behavior Mode: WANDER (autonomous), GROUPED (standing in a cluster),
    EMOTING (transient one-shot like hug)
  - animation clip: "idle" | "walk" | "jump" | "hug", derived from mode,
    velocity, and whether the character is airborne.

Coordinate convention (see docs/design/sidescroller-contract.md): ``pos`` is the
character's feet -- ``pos.x`` is the horizontal center, ``pos.y`` is the y of the
surface it stands on. Smaller y is higher on screen, so jumping is a negative y
velocity and gravity is positive.
"""

from __future__ import annotations

import random
import time
from enum import Enum, auto

import pygame
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import SpriteSet
from twitch_playground.sim import steering
from twitch_playground.sim.platforms import Platform, landing_surface


class Mode(Enum):
    WANDER = auto()
    GROUPED = auto()
    EMOTING = auto()


class Character:
    def __init__(
        self,
        username: str,
        pos: tuple[float, float],
        sprites: SpriteSet,
        nameplate: pygame.Surface,
    ) -> None:
        self.username = username
        self.pos = Vector2(pos)
        self.velocity = Vector2(0, 0)
        self.sprites = sprites
        self.nameplate = nameplate

        self.mode = Mode.WANDER
        self._prev_mode = Mode.WANDER  # restored after an EMOTING clip
        self.group_id: int | None = None
        self.group_slot: Vector2 | None = None  # target standing position

        # Surface the feet currently rest on; None means airborne. A character
        # spawned by World starts on the ground, but we resolve the actual
        # Platform object lazily on the first update once we have the level.
        self.platform: Platform | None = None

        self.clip = "idle"
        self.frame_index = 0.0
        self.emote_timer = 0.0

        self._facing = random.choice((-1, 1))  # horizontal stroll direction
        self._pause_timer = 0.0  # > 0 while taking an idle pause

        self.last_interaction = time.monotonic()

    # --- lifecycle / commands -------------------------------------------------

    def touch(self) -> None:
        self.last_interaction = time.monotonic()

    def trigger_hug(self) -> None:
        if self.mode is not Mode.EMOTING:
            self._prev_mode = self.mode
        self.mode = Mode.EMOTING
        self.clip = "hug"
        self.frame_index = 0.0
        self.emote_timer = settings.HUG_DURATION
        self.touch()

    def set_grouped(self, gid: int, slot: Vector2) -> None:
        self.group_id = gid
        self.group_slot = Vector2(slot)
        if self.mode is not Mode.EMOTING:
            self.mode = Mode.GROUPED
        self._prev_mode = Mode.GROUPED
        self.touch()

    def set_wander(self) -> None:
        self.group_id = None
        self.group_slot = None
        if self.mode is not Mode.EMOTING:
            self.mode = Mode.WANDER
        self._prev_mode = Mode.WANDER
        self.touch()

    # --- per-frame update -----------------------------------------------------

    def update(
        self,
        dt: float,
        neighbor_positions: list[Vector2],
        platforms: list[Platform],
    ) -> None:
        # On the very first frame we know nothing about the level geometry, so
        # snap onto whatever surface is directly under the feet.
        if self.platform is None and self.velocity.y == 0:
            self.platform = _surface_at(platforms, self.pos.x, self.pos.y)

        if self.mode is Mode.EMOTING:
            self._update_emoting(dt, platforms)
            return

        if self.mode is Mode.GROUPED:
            self._move_toward_slot(dt, platforms)
        else:
            self._wander(dt, neighbor_positions, platforms)

        self._update_clip()
        self._advance_anim(dt)

    def _wander(
        self,
        dt: float,
        neighbor_positions: list[Vector2],
        platforms: list[Platform],
    ) -> None:
        grounded = self.platform is not None
        pausing = False

        if grounded:
            if self._pause_timer > 0:
                self._pause_timer -= dt
                pausing = self._pause_timer > 0
                if not pausing:
                    self._facing = random.choice((-1, 1))  # head off afresh
            elif random.random() < settings.JUMP_CHANCE * dt:
                self.velocity.y = -settings.JUMP_SPEED  # hop -> becomes airborne
                self.platform = None
                grounded = False
            elif random.random() < settings.IDLE_CHANCE * dt:
                self._pause_timer = random.uniform(
                    settings.IDLE_PAUSE_MIN, settings.IDLE_PAUSE_MAX
                )
                pausing = True

        # Horizontal velocity: stroll unless paused, plus a separation nudge.
        walk = 0.0 if pausing else self._facing * settings.WALK_SPEED
        self.velocity.x = walk + steering.separation_push(self.pos, neighbor_positions)

        # Vertical velocity: pinned to the surface while grounded, else gravity.
        if self.platform is not None:
            self.velocity.y = 0.0
        else:
            self.velocity.y += settings.GRAVITY * dt

        prev_feet_y = self.pos.y
        self.pos += self.velocity * dt
        self._apply_horizontal_bounds()

        # Landing: only while airborne and descending can we catch a surface.
        if self.platform is None:
            landed = landing_surface(platforms, prev_feet_y, self.pos.y, self.pos.x)
            if landed is not None:
                self.pos.y = landed.top
                self.velocity.y = 0.0
                self.platform = landed

    def _apply_horizontal_bounds(self) -> None:
        """Keep grounded characters on their platform and everyone on screen.

        Grounded characters turn around at their platform's edges (clamped to
        the screen walls); airborne characters only clamp to the walls so they
        can still drift off a ledge and fall to a lower tier.
        """
        m = settings.WALL_MARGIN
        low, high = m, settings.SCREEN_W - m
        if self.platform is not None:
            low = max(low, self.platform.left)
            high = min(high, self.platform.right)
        if self.pos.x < low:
            self.pos.x = low
            self._facing = 1
            self.velocity.x = abs(self.velocity.x)
        elif self.pos.x > high:
            self.pos.x = high
            self._facing = -1
            self.velocity.x = -abs(self.velocity.x)

    def _move_toward_slot(self, dt: float, platforms: list[Platform]) -> None:
        if self.group_slot is None:
            return
        # The slot sits on a platform (slot.y == that platform's top), so resolve
        # and remember it -- this keeps us "grounded" (not playing the jump clip).
        self.platform = _surface_at(platforms, self.group_slot.x, self.group_slot.y)
        to_slot = self.group_slot - self.pos
        dist = to_slot.length()
        if dist <= settings.GROUP_ARRIVE_RADIUS:
            self.velocity = Vector2(0, 0)
            self.pos = Vector2(self.group_slot)
            return
        self.velocity = to_slot.normalize() * settings.WALK_SPEED
        step = self.velocity * dt
        if step.length() >= dist:  # don't overshoot the slot
            self.pos = Vector2(self.group_slot)
            self.velocity = Vector2(0, 0)
        else:
            self.pos += step

    def _update_emoting(self, dt: float, platforms: list[Platform]) -> None:
        # Stationary while emoting: ease any horizontal motion to a stop. If we
        # were hugged mid-hop, keep falling so we settle onto a surface.
        self.velocity.x *= 0.6
        if self.platform is None:
            self.velocity.y += settings.GRAVITY * dt
            prev_feet_y = self.pos.y
            self.pos += self.velocity * dt
            landed = landing_surface(platforms, prev_feet_y, self.pos.y, self.pos.x)
            if landed is not None:
                self.pos.y = landed.top
                self.velocity.y = 0.0
                self.platform = landed
        else:
            self.velocity.y = 0.0
            self.pos.x += self.velocity.x * dt

        self.emote_timer -= dt
        if self.emote_timer <= 0:
            self.mode = self._prev_mode
            self.clip = "idle"
            self.frame_index = 0.0
        self._advance_anim(dt)

    def _update_clip(self) -> None:
        if self.platform is None:
            want = "jump"
        elif abs(self.velocity.x) > settings.WALK_THRESHOLD:
            want = "walk"
        else:
            want = "idle"
        if want != self.clip:
            self.clip = want
            self.frame_index = 0.0

    def _advance_anim(self, dt: float) -> None:
        frames = self.sprites.clip(self.clip)
        self.frame_index = (self.frame_index + settings.ANIM_FPS * dt) % len(frames)

    # --- rendering ------------------------------------------------------------

    @property
    def surface(self) -> pygame.Surface:
        frames = self.sprites.clip(self.clip)
        return frames[int(self.frame_index) % len(frames)]


def _surface_at(platforms: list[Platform], x: float, y: float) -> Platform | None:
    """The platform whose top is at ``y`` (within a small tolerance) under ``x``.

    Used to bind a character to the surface it is standing on when we are placed
    there directly rather than by falling onto it (spawn, group slots)."""
    for p in platforms:
        if p.contains_x(x) and abs(p.top - y) <= 1.0:
            return p
    return None
