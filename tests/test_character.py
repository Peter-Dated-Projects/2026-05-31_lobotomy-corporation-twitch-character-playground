"""Character physics + clip-selection behaviour, exercised headlessly.

Randomness in WANDER (hops, idle pauses) is silenced via the ``calm`` fixture so
each test asserts an exact, frame-rate-independent outcome.
"""

from __future__ import annotations

import pygame

from twitch_playground import settings
from twitch_playground.sim.character import Character, Mode
from twitch_playground.sim.personality import Personality, personality_for
from twitch_playground.sim.platforms import default_level


def test_grounded_character_stays_on_its_surface(make_char, calm):
    level = default_level()
    ground = level[0]
    char = make_char(x=50.0)
    for _ in range(300):
        char.update(1 / 60, [], level)
    assert char.platform is ground
    assert char.pos.y == settings.GROUND_TOP
    assert char.velocity.y == 0.0


def test_forced_jump_rises_then_lands_back_on_ground(make_char, calm, monkeypatch):
    monkeypatch.setattr(settings, "WALK_SPEED", 0.0)  # purely vertical hop
    level = default_level()
    ground = level[0]
    # x=50 sits under the ground only -- clear of every floating platform span.
    char = make_char(x=50.0)
    char.update(1 / 120, [], level)  # bind to the ground first
    assert char.platform is ground

    char.velocity.y = -settings.JUMP_SPEED
    char.platform = None  # now airborne

    rose = False
    landed = False
    for _ in range(600):  # up to ~5s of sim time at dt=1/120
        char.update(1 / 120, [], level)
        if char.pos.y < settings.GROUND_TOP - 50:
            rose = True
        if char.platform is not None:
            landed = True
            break

    assert rose, "character never gained meaningful height"
    assert landed, "character never landed"
    assert char.platform is ground
    assert char.pos.y == settings.GROUND_TOP
    assert char.velocity.y == 0.0


def test_clip_is_jump_while_airborne(make_char, calm):
    level = default_level()
    char = make_char(x=50.0, y=settings.GROUND_TOP - 130)  # up in the air
    char.platform = None
    char.velocity.y = -300.0  # rising, so it won't land this frame
    char.update(1 / 60, [], level)
    assert char.platform is None
    assert char.clip == "jump"


def test_clip_is_walk_while_strolling_on_a_surface(make_char, calm):
    level = default_level()
    char = make_char(x=480.0)
    # Velocity now eases up over a few frames instead of snapping to full speed,
    # so give it time to cross WALK_THRESHOLD before asserting the walk clip.
    for _ in range(15):
        char.update(1 / 60, [], level)
    assert char.platform is not None
    assert abs(char.velocity.x) > settings.WALK_THRESHOLD
    assert char.clip == "walk"


def test_clip_is_idle_while_paused_on_a_surface(make_char, calm):
    level = default_level()
    char = make_char(x=480.0)
    char.update(1 / 60, [], level)  # bind + start strolling
    char._pause_timer = 5.0  # force an idle pause
    # While paused the desired velocity is 0; easing brings velocity.x to a true
    # zero within a few frames (steer_toward lands exactly when within the cap).
    for _ in range(30):
        char.update(1 / 60, [], level)
    assert char.platform is not None
    assert char.velocity.x == 0.0
    assert char.clip == "idle"


def test_velocity_eases_rather_than_snapping(make_char, calm, monkeypatch):
    # Freeze the wander heading so the test drives a fixed desired velocity.
    monkeypatch.setattr(settings, "WANDER_DISPLACE", 0.0)
    monkeypatch.setattr(settings, "WANDER_REORIENT_CHANCE", 0.0)
    level = default_level()
    char = make_char(x=480.0)
    char.update(1 / 60, [], level)  # bind to the ground
    char.velocity.x = 0.0
    char._wander_heading = settings.WALK_SPEED  # want full-speed rightward stroll

    char.update(1 / 60, [], level)
    # A single frame must NOT teleport to full speed -- it eases toward it.
    assert 0.0 < char.velocity.x < settings.WALK_SPEED
    after_one = char.velocity.x

    for _ in range(30):
        char.update(1 / 60, [], level)
    # Given time it ramps up, and never exceeds the MAX_SPEED magnitude cap.
    assert char.velocity.x > after_one
    assert abs(char.velocity.x) <= settings.MAX_SPEED


def test_facing_follows_velocity_with_deadzone(make_char, calm, monkeypatch):
    monkeypatch.setattr(settings, "WANDER_DISPLACE", 0.0)
    monkeypatch.setattr(settings, "WANDER_REORIENT_CHANCE", 0.0)
    level = default_level()
    char = make_char(x=480.0)
    char.update(1 / 60, [], level)

    # A clear rightward stroll commits facing right.
    char._wander_heading = settings.WALK_SPEED
    for _ in range(20):
        char.update(1 / 60, [], level)
    assert char.velocity.x > settings.WALK_THRESHOLD
    assert char.facing == 1

    # A clear leftward heading flips facing left.
    char._wander_heading = -settings.WALK_SPEED
    for _ in range(20):
        char.update(1 / 60, [], level)
    assert char.velocity.x < -settings.WALK_THRESHOLD
    assert char.facing == -1

    # Easing to a near-idle stop keeps velocity below the deadzone, so facing
    # must HOLD its last value rather than strobe.
    char._wander_heading = 0.0
    for _ in range(20):
        char.update(1 / 60, [], level)
    assert abs(char.velocity.x) <= settings.WALK_THRESHOLD
    assert char.facing == -1


def test_emoting_plays_hug_then_reverts(make_char, calm):
    level = default_level()
    char = make_char(x=50.0)
    char.update(1 / 60, [], level)  # ground it
    prior_mode = char.mode

    char.trigger_hug()
    assert char.mode is Mode.EMOTING
    assert char.clip == "hug"

    # Run well past HUG_DURATION; the emote must end and behaviour resume.
    steps = int((settings.HUG_DURATION + 0.5) / (1 / 60)) + 1
    for _ in range(steps):
        char.update(1 / 60, [], level)

    assert char.mode is prior_mode  # back to WANDER, not stuck EMOTING
    assert char.clip != "hug"


# --- personality (L4) ---------------------------------------------------------


def test_persona_defaults_to_username_derived(make_char):
    """A Character built without an explicit persona derives one from its
    username, so a bare Character is still deterministically seeded."""
    char = make_char(username="zelda")
    assert char.persona == personality_for("zelda")


def test_persona_injection_overrides_default(sprites):
    """World.spawn injects the persona (mirroring sprites/nameplate); an injected
    persona is used verbatim rather than re-derived."""
    p = Personality(sociability=0.1, independence=0.9, restlessness=0.5)
    nameplate = pygame.Surface((10, 6), pygame.SRCALPHA)
    char = Character("x", (50, settings.GROUND_TOP), sprites, nameplate, persona=p)
    assert char.persona is p


def test_tick_autonomy_fires_on_the_decide_interval(make_char, monkeypatch):
    """The decision gate is low-frequency: it does not fire every frame, but does
    fire (and re-arm) once the decide interval elapses."""
    monkeypatch.setattr(settings, "DECIDE_INTERVAL", 0.4)
    char = make_char()
    char._manual_hold = 0.0
    char._decide_timer = settings.DECIDE_INTERVAL
    # One short frame is far below the interval -> not yet due.
    assert char.tick_autonomy(0.05) is False
    # Over a full second of 0.05s frames it must fire at least once.
    assert any(char.tick_autonomy(0.05) for _ in range(20))


def test_manual_hold_suppresses_the_decision(make_char):
    """A held character never reports a decision as due, even with the decide
    timer already elapsed -- this is what keeps a viewer command from being
    autonomously undone."""
    char = make_char()
    char.hold_autonomy()
    char._decide_timer = 0.0  # a decision would otherwise be due immediately
    assert char.tick_autonomy(1 / 60) is False
    assert char._manual_hold > 0.0


def test_dwell_clock_resets_when_state_changes(make_char):
    """The time-in-state clock accrues while the mode is stable and resets when
    the character crosses between WANDER and GROUPED (the dwell dead-band)."""
    char = make_char()  # starts WANDER
    char.tick_autonomy(1.0)
    assert char._state_elapsed >= 1.0
    char.mode = Mode.GROUPED
    char.tick_autonomy(1 / 60)
    assert char._state_elapsed == 0.0
