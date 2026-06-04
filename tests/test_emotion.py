"""Emotion model (L5): decay, proximity-weighted contagion, face quantization
with hysteresis, and how the mood modulates movement -- all exercised headlessly.

The continuous (valence, arousal) state and the contagion math are pure scalar
work, so most tests drive ``_update_emotion`` directly with a hand-built neighbour
list rather than running the whole World, keeping each assertion exact.
"""

from __future__ import annotations

import pygame
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.sim.character import Character, Neighbor, _emotion_traits


def _neighbor(
    pos: Vector2,
    *,
    arousal: float = 0.0,
    valence: float = 0.0,
    expressiveness: float = 1.0,
) -> Neighbor:
    """A neighbour snapshot for contagion tests (facing/vx are irrelevant here)."""
    return Neighbor(pos, 1, 0.0, arousal, valence, expressiveness)


# --- decay --------------------------------------------------------------------


def test_emotion_decays_back_to_neutral(make_char):
    """With nobody around, an emotional spike relaxes toward neutral -- the
    legibility mechanic that stops faces from latching forever."""
    char = make_char()
    char.arousal = 0.8
    char.valence = -0.6
    for _ in range(300):  # ~5s at dt=1/60
        char._update_emotion(1 / 60, [])
    assert char.arousal < 0.05
    assert abs(char.valence) < 0.05


def test_decay_outruns_a_lone_resting_neighbour(make_char):
    """A single calm neighbour cannot, on its own, keep a character agitated:
    decay must dominate at the crowd's resting state or panic becomes permanent."""
    char = make_char(x=200.0)
    char.arousal = 0.9
    neutral = [_neighbor(Vector2(210.0, char.pos.y), arousal=0.0, valence=0.0)]
    for _ in range(300):
        char._update_emotion(1 / 60, neutral)
    # The tiny crowding bump from one neighbour does not overpower decay.
    assert char.arousal < 0.2


# --- contagion ----------------------------------------------------------------


def test_contagion_spreads_a_spike_to_a_near_neighbour_with_lag(make_char):
    """An agitated neighbour infects a calm character -- but NOT instantly: the
    spread takes several frames (the lag that makes a ripple read as a ripple)."""
    char = make_char(x=200.0)
    char.susceptibility = 1.0
    char.arousal = 0.0
    # A loud, highly-aroused neighbour well within the contagion radius.
    hot = [_neighbor(Vector2(220.0, char.pos.y), arousal=0.9, expressiveness=1.0)]

    char._update_emotion(1 / 60, hot)
    after_one = char.arousal
    # Lag: a single frame catches only a little of the neighbour's arousal.
    assert 0.0 < after_one < 0.1

    for _ in range(120):
        char._update_emotion(1 / 60, hot)
    # Over time it climbs well past the one-frame value...
    assert char.arousal > after_one
    # ...but decay keeps it from fully matching the source (never a hard latch).
    assert char.arousal < 0.9


def test_contagion_falls_off_with_distance(make_char):
    """A neighbour beyond CONTAGION_RADIUS does not infect at all; the same
    neighbour up close does -- proximity is the channel strength."""
    near = make_char(x=200.0)
    far = make_char(x=200.0)
    near.susceptibility = far.susceptibility = 1.0
    inside = [_neighbor(Vector2(220.0, near.pos.y), arousal=0.9)]
    outside_x = 200.0 + settings.CONTAGION_RADIUS + 20.0
    outside = [_neighbor(Vector2(outside_x, far.pos.y), arousal=0.9)]
    for _ in range(30):
        near._update_emotion(1 / 60, inside)
        far._update_emotion(1 / 60, outside)
    assert near.arousal > 0.0
    assert far.arousal == 0.0


def test_own_record_does_not_self_infect(make_char):
    """The shared neighbour list World hands in includes the character's OWN
    record (distance 0); contagion must skip it so a character does not pull
    itself toward its own current mood."""
    char = make_char(x=200.0)
    char.arousal = 0.5
    own = [_neighbor(Vector2(char.pos), arousal=0.5)]  # same position -> self
    before = char.arousal
    char._update_emotion(1 / 60, own)
    # Only decay (+ no crowd bump, since the sole record is self) moved it.
    assert char.arousal < before


# --- face quantization + hysteresis ------------------------------------------


def test_emotion_face_quantizes_to_three_states(make_char):
    char = make_char()
    char.valence, char.arousal = 0.0, 0.0
    assert char.emotion_face() == "default"

    char._emotion_face = "default"
    char.valence, char.arousal = 0.2, 0.6  # high arousal, positive valence
    assert char.emotion_face() == "battle"

    char._emotion_face = "default"
    char.valence, char.arousal = -0.5, 0.5  # distressed + agitated
    assert char.emotion_face() == "panic"


def test_emotion_face_has_hysteresis(make_char):
    """A face held through a small dip back across its enter boundary -- the
    anti-strobe guarantee. Same mood reads 'default' from a default start but
    'panic' once panic is already showing."""
    cold = make_char()
    warm = make_char()
    # A mood inside the panic hysteresis band: arousal is past the EXIT threshold
    # (so panic holds) but below the stricter ENTER threshold (so panic can't be
    # freshly entered from it).
    v, a = -0.30, 0.30
    assert a > settings.PANIC_AROUSAL_EXIT and a < settings.PANIC_AROUSAL_ENTER
    assert v < settings.PANIC_VALENCE_EXIT

    cold.valence, cold.arousal = v, a
    cold._emotion_face = "default"
    assert cold.emotion_face() == "default"  # not enough to ENTER panic

    warm.valence, warm.arousal = v, a
    warm._emotion_face = "panic"
    assert warm.emotion_face() == "panic"  # already panicking -> HOLDS


def test_emotion_face_is_idempotent(make_char):
    """Re-calling with an unchanged mood is stable (rendering may read it more
    than once per frame)."""
    char = make_char()
    char.valence, char.arousal = -0.5, 0.6
    first = char.emotion_face()
    assert char.emotion_face() == first
    assert char.emotion_face() == first


# --- movement modulation ------------------------------------------------------


def test_arousal_speeds_up_movement(make_char, calm, monkeypatch):
    """An aroused character walks faster than a calm one -- arousal lifts both the
    desired speed and the magnitude cap."""
    monkeypatch.setattr(settings, "WANDER_DISPLACE", 0.0)
    monkeypatch.setattr(settings, "WANDER_REORIENT_CHANCE", 0.0)
    monkeypatch.setattr(settings, "EMOTION_DECAY_PER_SEC", 1.0)  # hold the arousal
    from twitch_playground.sim.platforms import default_level

    level = default_level()
    calm_char = make_char(x=480.0)
    hot_char = make_char(x=480.0)
    calm_char.update(1 / 60, [], level)
    hot_char.update(1 / 60, [], level)
    calm_char._wander_heading = hot_char._wander_heading = settings.WALK_SPEED
    hot_char.arousal = 1.0

    for _ in range(40):
        calm_char.arousal = 0.0  # keep the baseline genuinely calm
        hot_char.arousal = 1.0
        calm_char.update(1 / 60, [], level)
        hot_char.update(1 / 60, [], level)

    assert hot_char.velocity.x > calm_char.velocity.x + 10.0
    assert calm_char.velocity.x <= settings.MAX_SPEED


def test_low_valence_widens_separation(make_char, calm, monkeypatch):
    """A distressed character pushes away from a close neighbour harder than a
    happy one (withdraw / want more space)."""
    monkeypatch.setattr(settings, "WANDER_DISPLACE", 0.0)
    monkeypatch.setattr(settings, "WANDER_REORIENT_CHANCE", 0.0)
    monkeypatch.setattr(settings, "EMOTION_DECAY_PER_SEC", 1.0)  # hold the valence
    # Snap velocity straight to the desired value so one frame is decisive.
    monkeypatch.setattr(settings, "MAX_FORCE", 100_000.0)
    monkeypatch.setattr(settings, "MAX_SPEED", 100_000.0)
    from twitch_playground.sim.platforms import default_level

    level = default_level()
    distressed = make_char(x=400.0)
    happy = make_char(x=400.0)
    distressed.update(1 / 60, [], level)
    happy.update(1 / 60, [], level)
    distressed._wander_heading = happy._wander_heading = 0.0  # only the crowd nudge
    distressed.valence = -1.0
    happy.valence = 1.0

    # A neighbour just to the right, in-band and inside the separation radius.
    # expressiveness 0 so it does not also drag valence around via contagion.
    right = Vector2(415.0, settings.GROUND_TOP)
    nb = lambda c: [Neighbor(right, 1, 0.0, 0.0, 0.0, 0.0)]  # noqa: E731

    distressed.valence = -1.0
    distressed.update(1 / 60, nb(distressed), level)
    happy.valence = 1.0
    happy.update(1 / 60, nb(happy), level)

    # Both are pushed left (negative); the distressed one harder.
    assert distressed.velocity.x < happy.velocity.x < 0.0


# --- seeded traits ------------------------------------------------------------


def test_emotion_traits_are_deterministic_and_in_band():
    a1 = _emotion_traits("someviewer")
    a2 = _emotion_traits("someviewer")
    assert a1 == a2  # stable across calls (md5, not per-process hash)
    for v in (*a1, *_emotion_traits("another")):
        assert settings.EMOTION_TRAIT_MIN <= v <= 1.0


def test_emotion_traits_decorrelated_from_persona_salt():
    """The emotion seed uses a different salt than the persona seed, so two
    distinct usernames don't get lockstep traits and the emotion digest differs
    from what the persona digest would produce."""
    assert _emotion_traits("viewerA") != _emotion_traits("viewerB")


def test_character_seeds_emotion_traits_from_username(make_char):
    char = make_char(username="zelda")
    assert (char.susceptibility, char.expressiveness) == _emotion_traits("zelda")
    assert char.valence == 0.0 and char.arousal == 0.0  # resting at spawn


# --- command impulses ---------------------------------------------------------


def test_hug_lifts_valence(make_char):
    char = make_char()
    before = char.valence
    char.trigger_hug()
    assert char.valence > before


# --- renderer fallback contract -----------------------------------------------


def test_sprite_set_falls_back_to_default_for_missing_emotion(sprites):
    """A SpriteSet with only default-emotion clips (the placeholder / asset-absent
    path) still serves every emotion key, returning the default frames."""
    assert sprites.clip("walk", "panic") == sprites.clip("walk", "default")
    assert sprites.clip("walk", "battle") == sprites.clip("walk")


def test_surface_renders_at_any_emotion_face(make_char):
    """Character.surface picks frames by the live emotion face and never raises,
    even on placeholder art that has no per-emotion variants."""
    char = make_char()
    char.valence, char.arousal = -0.5, 0.6  # panic
    assert isinstance(char.surface, pygame.Surface)
    char.valence, char.arousal = 0.0, 0.0  # default
    assert isinstance(char.surface, pygame.Surface)
