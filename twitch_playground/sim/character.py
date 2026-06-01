"""A single on-screen character bound to a Twitch username.

Two orthogonal axes of state:
  - behavior Mode: WANDER (autonomous), GROUPED (standing in a cluster),
    EMOTING (transient one-shot like hug)
  - animation clip: "idle" | "walk" | "hug", derived from mode + velocity
"""

from __future__ import annotations

import time
from enum import Enum, auto

import pygame
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import SpriteSet
from twitch_playground.sim import steering


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

        self.clip = "idle"
        self.frame_index = 0.0
        self.wander_angle = 0.0
        self.emote_timer = 0.0

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

    def update(self, dt: float, neighbor_positions: list[Vector2]) -> None:
        if self.mode is Mode.EMOTING:
            self.velocity *= 0.6  # ease to a stop while emoting
            self.pos += self.velocity * dt
            self.emote_timer -= dt
            if self.emote_timer <= 0:
                self.mode = self._prev_mode
                self.clip = "idle"
                self.frame_index = 0.0
            self._advance_anim(dt)
            return

        if self.mode is Mode.GROUPED:
            self._move_toward_slot(dt)
        else:
            self._wander(dt, neighbor_positions)

        self._update_clip_from_velocity()
        self._advance_anim(dt)

    def _wander(self, dt: float, neighbor_positions: list[Vector2]) -> None:
        steer, self.wander_angle = steering.wander_force(self.velocity, self.wander_angle, dt)
        self.velocity += steer * dt
        self.velocity += steering.separation_force(self.pos, neighbor_positions) * dt
        if self.velocity.length() > settings.MAX_SPEED:
            self.velocity.scale_to_length(settings.MAX_SPEED)
        self.pos += self.velocity * dt
        steering.clamp_to_bounds(self.pos, self.velocity, settings.SCREEN_W, settings.SCREEN_H)

    def _move_toward_slot(self, dt: float) -> None:
        if self.group_slot is None:
            return
        to_slot = self.group_slot - self.pos
        dist = to_slot.length()
        if dist <= settings.GROUP_ARRIVE_RADIUS:
            self.velocity = Vector2(0, 0)
            self.pos = Vector2(self.group_slot)
            return
        self.velocity = to_slot.normalize() * settings.MAX_SPEED
        step = self.velocity * dt
        if step.length() >= dist:  # don't overshoot the slot
            self.pos = Vector2(self.group_slot)
            self.velocity = Vector2(0, 0)
        else:
            self.pos += step

    def _update_clip_from_velocity(self) -> None:
        moving = self.velocity.length() > settings.WALK_THRESHOLD
        want = "walk" if moving else "idle"
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
