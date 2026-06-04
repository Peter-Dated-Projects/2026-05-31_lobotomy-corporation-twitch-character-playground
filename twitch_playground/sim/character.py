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

import hashlib
import random
import time
from enum import Enum, auto
from typing import NamedTuple

import pygame
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import SpriteSet
from twitch_playground.sim import steering
from twitch_playground.sim.personality import Personality, personality_for
from twitch_playground.sim.platforms import Platform, landing_surface


class Mode(Enum):
    WANDER = auto()
    GROUPED = auto()
    EMOTING = auto()


class Neighbor(NamedTuple):
    """The per-frame snapshot of one character, built ONCE by ``World.update``
    and shared by every consumer so the neighbour list is scanned a single time.

    Supersets the L3 steering record ``(pos, facing, vx)`` with the L5 emotion
    fields ``(arousal, valence, expressiveness)`` so emotional contagion reuses
    the same shared scan -- no extra spatial query. The pure steering helpers in
    ``sim.steering`` read only the first three fields and duck-type their input,
    so this richer record is a drop-in everywhere ``steering.Neighbor`` was used.

    ``pos`` is a frame-start copy (so a rule never sees a neighbour move
    mid-frame); ``facing``/``vx`` carry heading for alignment; the emotion fields
    let a neighbour infect this character in ``Character._update_emotion``.
    """

    pos: Vector2
    facing: int
    vx: float
    arousal: float
    valence: float
    expressiveness: float


# Salt prefix for the emotion-trait digest. Deliberately DIFFERENT from both the
# appearance hash (bare username, in assign_character) and the persona hash
# ("persona:", in sim/personality.py) so a character's emotional temperament is
# decorrelated from its look AND its grouping behaviour.
_EMOTION_SALT = "emotion:"
_EMOTION_WINDOW = 0xFFFF  # 16-bit window carved from the md5 digest


def _emotion_traits(username: str) -> tuple[float, float]:
    """Deterministically derive ``(susceptibility, expressiveness)`` in
    ``[EMOTION_TRAIT_MIN, 1.0]`` from ``username``.

    susceptibility = how much my neighbours' mood moves me; expressiveness = how
    much I move theirs. md5 (not Python's per-process-salted ``hash``) so a given
    viewer is the same calm anchor or panic amplifier across restarts, matching
    the stability guarantee of the appearance/persona seeds. Two independent
    16-bit windows of one digest, mapped into the [MIN, 1.0] band so nobody is a
    perfect non-conductor.
    """
    digest = hashlib.md5(f"{_EMOTION_SALT}{username}".encode("utf-8")).hexdigest()
    h = int(digest, 16)
    raw_sus = ((h >> 0) & _EMOTION_WINDOW) / _EMOTION_WINDOW
    raw_exp = ((h >> 16) & _EMOTION_WINDOW) / _EMOTION_WINDOW
    lo = settings.EMOTION_TRAIT_MIN
    span = 1.0 - lo
    return lo + span * raw_sus, lo + span * raw_exp


class Character:
    def __init__(
        self,
        username: str,
        pos: tuple[float, float],
        sprites: SpriteSet,
        nameplate: pygame.Surface,
        persona: Personality | None = None,
    ) -> None:
        self.username = username
        self.pos = Vector2(pos)
        self.velocity = Vector2(0, 0)
        self.sprites = sprites
        self.nameplate = nameplate
        # Seeded personality. Normally injected by World.spawn (mirroring how
        # sprites/nameplate are), but defaults to deriving from the username so a
        # bare Character (tests) still has a stable persona.
        self.persona = persona if persona is not None else personality_for(username)

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

        self._facing = random.choice((-1, 1))  # last committed facing (-1 / 1)
        # Persistent wander heading: a signed desired speed (px/s) that drifts
        # coherently each frame, replacing the old random.choice direction flip.
        # Start strolling at full speed in the initial facing direction.
        self._wander_heading = self._facing * settings.WALK_SPEED
        self._pause_timer = 0.0  # > 0 while taking an idle pause

        # Autonomous join/leave bookkeeping (L4). The decision runs on a low-
        # frequency tick (World drives it); these track WHEN it may next fire.
        # A random initial phase spreads decisions across frames so the whole
        # crowd does not re-evaluate in lockstep.
        self._decide_timer = random.uniform(0.0, settings.DECIDE_INTERVAL)
        self._manual_hold = 0.0  # > 0 while a viewer command suppresses autonomy
        self._state_elapsed = 0.0  # s spent in the current WANDER/GROUPED state
        self._autonomy_mode = self.mode  # last WANDER/GROUPED seen, for dwell reset

        # Emotion (L5): a continuous mood orthogonal to Mode -- a character can be
        # panicked while wandering. Updated every frame (decay + contagion +
        # crowding) and quantized to a face. susceptibility/expressiveness are the
        # per-agent contagion knobs, seeded from the username so a viewer is a
        # consistent calm anchor or panic amplifier across restarts.
        self.valence = 0.0  # -1 distressed, 0 neutral, +1 happy
        self.arousal = 0.0  # 0 calm, 1 maxed out
        self.susceptibility, self.expressiveness = _emotion_traits(username)
        self._emotion_face = "default"  # last quantized face (held for hysteresis)

        self.last_interaction = time.monotonic()

    @property
    def facing(self) -> int:
        """Horizontal facing for the renderer: ``1`` faces right (the unflipped
        sheet pose), ``-1`` faces left. Read-only; updated from velocity with a
        WALK_THRESHOLD deadzone so a near-idle character does not strobe. See
        docs/design/sidescroller-contract.md (Sim exposes it, render consumes)."""
        return self._facing

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
        self.apply_emotion(d_valence=settings.HUG_VALENCE_IMPULSE)  # a hug lifts the mood
        self.touch()

    def apply_emotion(self, d_valence: float = 0.0, d_arousal: float = 0.0) -> None:
        """Apply an instantaneous, clamped emotion impulse (an appraised event).

        Chat commands route through here: a command IS the appraised event, so we
        skip OCC goals/standards machinery and just nudge the mood, clamped to the
        valid ranges. Decay (in ``_update_emotion``) then relaxes it back over the
        next few seconds, so an impulse reads as a spike, not a latch.
        """
        self.valence = max(-1.0, min(1.0, self.valence + d_valence))
        self.arousal = max(0.0, min(1.0, self.arousal + d_arousal))

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

    # --- autonomy (L4) --------------------------------------------------------

    def hold_autonomy(self) -> None:
        """Suppress the autonomous join/leave check for ``MANUAL_HOLD_DURATION``.

        Called by World when a viewer issues an explicit !follow / !leave / !join /
        !hug so the AI does not immediately undo the command -- the viewer's
        intent is authoritative; autonomy only fills the silence.
        """
        self._manual_hold = settings.MANUAL_HOLD_DURATION

    def tick_autonomy(self, dt: float) -> bool:
        """Advance the decide / hold / dwell timers; return True iff an autonomous
        decision is due this frame.

        Drives three things: the manual-hold countdown (viewer override), the
        time-in-state clock used for the dwell dead-band (reset whenever we cross
        between WANDER and GROUPED -- an EMOTING blip does not reset it), and the
        low-frequency decide gate. Returns False while under a manual hold so a
        viewer command is never reverted; the caller still checks the dwell clock.
        """
        self._manual_hold = max(0.0, self._manual_hold - dt)

        relevant = (
            self.mode if self.mode in (Mode.WANDER, Mode.GROUPED) else self._autonomy_mode
        )
        if relevant is not self._autonomy_mode:
            self._autonomy_mode = relevant
            self._state_elapsed = 0.0
        else:
            self._state_elapsed += dt

        self._decide_timer -= dt
        if self._decide_timer > 0.0:
            return False
        self._decide_timer = settings.DECIDE_INTERVAL
        return self._manual_hold <= 0.0

    # --- per-frame update -----------------------------------------------------

    def update(
        self,
        dt: float,
        neighbors: list[Neighbor],
        platforms: list[Platform],
    ) -> None:
        # Emotion is orthogonal to Mode (a character can be panicked while
        # grouped or emoting), so tick it EVERY frame, before the mode branch.
        self._update_emotion(dt, neighbors)

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
            self._wander(dt, neighbors, platforms)

        self._update_clip()
        self._advance_anim(dt)

    # --- emotion (L5) ---------------------------------------------------------

    def _update_emotion(self, dt: float, neighbors: list[Neighbor]) -> None:
        """Advance the continuous (valence, arousal) mood one frame.

        Three sources, in order: (1) exponential decay toward neutral -- the
        single most important legibility mechanic, and the reason decay must
        outrun contagion or panic latches forever; (2) proximity-weighted
        contagion pulling toward neighbours' mood, scaled by my susceptibility
        and each sender's expressiveness (reuses the shared neighbour scan -- no
        new spatial query); (3) a mild crowding bump to arousal. Clamp last.

        Crowding uses the IN-RADIUS neighbour count, not ``len(neighbors)``: the
        shared list is every character in the world, so ``len`` would bump arousal
        from far-away strangers too.
        """
        decay = settings.EMOTION_DECAY_PER_SEC ** dt
        self.arousal *= decay
        self.valence *= decay

        radius = settings.CONTAGION_RADIUS
        tot_w = ar = va = 0.0
        nearby = 0
        for n in neighbors:
            d = self.pos.distance_to(n.pos)
            if d <= 0.0 or d > radius:  # d == 0 skips my own record in the list
                continue
            nearby += 1
            w = (1.0 - d / radius) * n.expressiveness  # closer + louder = stronger
            ar += w * n.arousal
            va += w * n.valence
            tot_w += w
        if tot_w > 0.0:
            # Clamp the step so a large dt can't overshoot past the neighbour mean.
            rate = min(1.0, settings.CONTAGION_RATE * self.susceptibility * dt)
            self.arousal += rate * (ar / tot_w - self.arousal)
            self.valence += rate * (va / tot_w - self.valence)

        self.arousal += settings.CROWD_AROUSAL * nearby * dt
        self.arousal = max(0.0, min(1.0, self.arousal))
        self.valence = max(-1.0, min(1.0, self.valence))

    def emotion_face(self) -> str:
        """Quantize the continuous mood to ``"default" | "battle" | "panic"`` with
        hysteresis so the rendered face does not strobe on a boundary.

        Each face uses looser EXIT thresholds while it is the current face than
        the ENTER thresholds used to reach it, so a value dipping back across the
        boundary holds the face instead of flickering. Priority panic > battle >
        default. Mutating + idempotent: re-calling with the same mood is stable.
        """
        cur = self._emotion_face
        v, a = self.valence, self.arousal
        if cur == "panic":
            panic = v < settings.PANIC_VALENCE_EXIT and a > settings.PANIC_AROUSAL_EXIT
        else:
            panic = v < settings.PANIC_VALENCE_ENTER and a > settings.PANIC_AROUSAL_ENTER
        if cur == "battle":
            battle = a > settings.BATTLE_AROUSAL_EXIT
        else:
            battle = a > settings.BATTLE_AROUSAL_ENTER
        face = "panic" if panic else "battle" if battle else "default"
        self._emotion_face = face
        return face

    def _wander(
        self,
        dt: float,
        neighbors: list[Neighbor],
        platforms: list[Platform],
    ) -> None:
        grounded = self.platform is not None
        pausing = False

        # Local crowd density (same-band neighbour count) drives the decision
        # block below and the speed slowdown: a packed platform shuffles, hops
        # less, and pauses more -- the crowd "hangs out" instead of marching.
        density = steering.local_density(self.pos, neighbors)

        # Restlessness scales the hop/idle cadence: a [0, RESTLESS_RATE_SPAN]
        # multiplier so the median character keeps ~the global rate while a calm
        # one barely fidgets and a restless one paces and pauses constantly --
        # visible per-character variety even before any grouping logic. Arousal
        # then layers on top: an agitated character hops more and pauses less
        # (it paces instead of taking idle breaks), a calm one the reverse.
        rest_mult = settings.RESTLESS_RATE_SPAN * self.persona.restlessness
        arousal_gain = 1.0 + settings.AROUSAL_RESTLESS_GAIN * self.arousal
        jump_mult = rest_mult * arousal_gain
        idle_mult = rest_mult / arousal_gain

        if grounded:
            if self._pause_timer > 0:
                self._pause_timer -= dt
                pausing = self._pause_timer > 0
                if not pausing:
                    # Coming out of a pause: pick a fresh meander direction by
                    # reorienting the heading (still eased into, never snapped).
                    self._wander_heading = (
                        random.uniform(-1.0, 1.0) * settings.WALK_SPEED
                    )
            elif (
                density < settings.CROWD_JUMP_DENSITY
                and random.random() < settings.JUMP_CHANCE * jump_mult * dt
            ):
                self.velocity.y = -settings.JUMP_SPEED  # hop -> becomes airborne
                self.platform = None
                grounded = False
            else:
                # Crowded characters pause more often (milling/hanging-out read);
                # restlessness scales how often this character pauses at all,
                # arousal suppresses it (agitated characters don't rest).
                idle_chance = settings.IDLE_CHANCE * idle_mult * (
                    1.0 + density * settings.CROWD_IDLE_DENSITY_GAIN
                )
                if random.random() < idle_chance * dt:
                    self._pause_timer = random.uniform(
                        settings.IDLE_PAUSE_MIN, settings.IDLE_PAUSE_MAX
                    )
                    pausing = True

        # Drift the wander heading coherently while actively strolling.
        if grounded and not pausing:
            self._wander_heading = steering.wander_heading(self._wander_heading, dt)

        # Desired horizontal velocity = wander heading (0 while paused), scaled
        # down by crowd density (SFM density response, floored so nobody
        # freezes), plus a separation-dominant crowd blend clamped to a max
        # nudge. Ease the actual velocity toward it instead of snapping, then
        # clamp to MAX_SPEED.
        speed_scale = max(
            settings.CROWD_MIN_SPEED_SCALE,
            1.0 - density * settings.CROWD_SLOWDOWN_PER_NEIGHBOR,
        )
        # Emotion modulates voluntary movement: arousal speeds it up (and lifts
        # the magnitude cap below so a panicked character actually outruns the
        # resting WALK_SPEED), while distress (negative valence) damps it back
        # down -- net effect: panicked = fast & erratic, sad = sluggish.
        emo_speed = 1.0 + settings.AROUSAL_SPEED_GAIN * self.arousal
        if self.valence < 0.0:
            emo_speed *= max(0.0, 1.0 + settings.VALENCE_SPEED_DAMP * self.valence)
        # Valence scales separation: distressed characters withdraw (want more
        # space, the flight read), happy ones tolerate a tighter cluster.
        sep_scale = max(0.0, 1.0 - settings.VALENCE_SEP_GAIN * self.valence)

        desired_vx = (
            0.0 if pausing else self._wander_heading * speed_scale * emo_speed
        )
        crowd = (
            settings.CROWD_SEP_WEIGHT
            * sep_scale
            * steering.separation_push(self.pos, neighbors)
            + settings.CROWD_COH_WEIGHT * steering.cohesion_pull(self.pos, neighbors)
            + settings.CROWD_ALI_WEIGHT * steering.alignment_nudge(self.pos, neighbors)
        )
        desired_vx += max(
            -settings.CROWD_MAX_NUDGE, min(settings.CROWD_MAX_NUDGE, crowd)
        )
        self.velocity.x = steering.steer_toward(
            self.velocity.x, desired_vx, settings.MAX_FORCE * dt
        )
        max_speed = settings.MAX_SPEED * emo_speed
        self.velocity.x = max(-max_speed, min(max_speed, self.velocity.x))

        # Vertical velocity: pinned to the surface while grounded, else gravity.
        if self.platform is not None:
            self.velocity.y = 0.0
        else:
            self.velocity.y += settings.GRAVITY * dt

        prev_feet_y = self.pos.y
        self.pos += self.velocity * dt
        self._apply_horizontal_bounds()
        self._update_facing()

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
        # Turn the *heading* around at the edge (so the eased velocity follows
        # it back inward) rather than hard-rerolling facing. A zero heading is
        # bumped to full WALK_SPEED so a character cannot stall against a wall.
        speed = abs(self._wander_heading) or settings.WALK_SPEED
        if self.pos.x < low:
            self.pos.x = low
            self._wander_heading = speed
            self.velocity.x = abs(self.velocity.x)
        elif self.pos.x > high:
            self.pos.x = high
            self._wander_heading = -speed
            self.velocity.x = -abs(self.velocity.x)

    def _update_facing(self) -> None:
        """Commit a new facing only when moving faster than WALK_THRESHOLD.

        The deadzone is the hysteresis that stops a near-idle character (nudged
        only by ``separation_push``) from flickering left/right: below the
        threshold the previous facing is held."""
        if abs(self.velocity.x) > settings.WALK_THRESHOLD:
            self._facing = 1 if self.velocity.x > 0 else -1

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
        # Arrive: full speed until within GROUP_SLOW_RADIUS, then scale the
        # desired speed down linearly with distance so the follower decelerates
        # into the slot instead of running flat-out then snapping. The
        # GROUP_ARRIVE_RADIUS check above is the final settle.
        speed = settings.WALK_SPEED
        if dist < settings.GROUP_SLOW_RADIUS:
            speed *= dist / settings.GROUP_SLOW_RADIUS
        desired = to_slot.normalize() * speed
        # Ease both axes toward the desired velocity (capped force), matching the
        # wander easing so grouped motion has the same weight.
        max_delta = settings.MAX_FORCE * dt
        self.velocity.x = steering.steer_toward(self.velocity.x, desired.x, max_delta)
        self.velocity.y = steering.steer_toward(self.velocity.y, desired.y, max_delta)
        step = self.velocity * dt
        if step.length() >= dist:  # don't overshoot the slot
            self.pos = Vector2(self.group_slot)
            self.velocity = Vector2(0, 0)
        else:
            self.pos += step
        self._update_facing()

    def _update_emoting(self, dt: float, platforms: list[Platform]) -> None:
        # Stationary while emoting: ease any horizontal motion to a stop. If we
        # were hugged mid-hop, keep falling so we settle onto a surface. The
        # decay is dt-based so it is identical at any frame rate.
        self.velocity.x *= settings.EMOTE_DECAY_PER_SEC ** dt
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
        # Select the frame list by the quantized emotion face; the provider holds
        # all three face variants per clip (and falls back to the resting face
        # when an emotion variant is absent, e.g. placeholder art).
        frames = self.sprites.clip(self.clip, self.emotion_face())
        return frames[int(self.frame_index) % len(frames)]


def _surface_at(platforms: list[Platform], x: float, y: float) -> Platform | None:
    """The platform whose top is at ``y`` (within a small tolerance) under ``x``.

    Used to bind a character to the surface it is standing on when we are placed
    there directly rather than by falling onto it (spawn, group slots)."""
    for p in platforms:
        if p.contains_x(x) and abs(p.top - y) <= 1.0:
            return p
    return None
