"""Seeded personality model (L4): determinism, range, decorrelation from the
appearance hash, and the deliberate distribution skew.

These run headlessly with no pygame -- personality is pure data + scalar math.
"""

from __future__ import annotations

from collections import defaultdict

from twitch_playground.assets.character_defs import assign_character
from twitch_playground.sim.personality import (
    Personality,
    join_threshold,
    leave_floor,
    personality_for,
)


def test_personality_is_deterministic_across_calls():
    """Same username -> identical traits, every time (md5-seeded, not salted
    hash()), so a viewer's personality is stable across process restarts."""
    a = personality_for("StreamerFan42")
    b = personality_for("StreamerFan42")
    assert a == b
    assert personality_for("someone_else") != a


def test_traits_are_in_unit_range():
    for i in range(1000):
        p = personality_for(f"viewer{i}")
        assert 0.0 <= p.sociability <= 1.0
        assert 0.0 <= p.independence <= 1.0
        assert 0.0 <= p.restlessness <= 1.0


def test_personality_is_decorrelated_from_appearance():
    """The persona digest is salted differently than assign_character, so viewers
    who LOOK the same do not all ACT the same. Across many names, at least one
    appearance bucket holds two names with different personalities."""
    buckets: dict[str, list[Personality]] = defaultdict(list)
    for i in range(500):
        u = f"viewer{i}"
        buckets[assign_character(u)].append(personality_for(u))

    collisions = [members for members in buckets.values() if len(members) >= 2]
    assert collisions, "expected some appearance collisions across 500 names"
    assert any(len(set(members)) > 1 for members in collisions), (
        "same-appearance viewers all share a personality -> the persona hash is "
        "not decorrelated from the appearance hash"
    )


def test_distribution_is_skewed_so_loners_are_a_minority():
    """The threshold-model insight is that the distribution shape (not the mean)
    decides whether crowds form. We up-skew sociability and down-skew independence
    so most characters readily join and genuine loners are a thin tail."""
    socs: list[float] = []
    inds: list[float] = []
    for i in range(2000):
        p = personality_for(f"u{i}")
        socs.append(p.sociability)
        inds.append(p.independence)
    n = len(socs)

    assert sum(socs) / n > 0.55, "sociability should be up-skewed (mostly social)"
    assert sum(inds) / n < 0.45, "independence should be down-skewed (few contrarians)"
    loner_fraction = sum(1 for x in inds if x > 0.7) / n
    assert loner_fraction < 0.25, "genuine loners must be a minority of the room"


def test_join_threshold_realises_granovetter():
    """A maximally sociable / dependent character joins a single neighbour
    (T == 1); a maximally independent one needs a near-mob."""
    sociable = Personality(sociability=1.0, independence=0.0, restlessness=0.5)
    loner = Personality(sociability=0.0, independence=1.0, restlessness=0.5)
    assert join_threshold(sociable) == 1
    assert join_threshold(loner) == 1 + 5  # 1 + round(1.0 * MAX_JOIN_THRESHOLD)


def test_leave_floor_is_strictly_below_join_threshold():
    """The dual-threshold dead-band: a character leaves at a strictly smaller
    crowd size than the one that pulls it in, so the boundary does not vibrate.
    A sociable character (T == 1) gets floor 0 and so never autonomously leaves."""
    for ind in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = Personality(sociability=0.5, independence=ind, restlessness=0.5)
        assert leave_floor(p) == join_threshold(p) - 1
    assert leave_floor(Personality(0.9, 0.0, 0.9)) == 0
