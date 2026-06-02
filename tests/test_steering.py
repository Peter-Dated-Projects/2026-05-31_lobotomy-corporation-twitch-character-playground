"""Pure-function tests for the horizontal separation nudge."""

from __future__ import annotations

from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.sim.steering import (
    Neighbor,
    alignment_nudge,
    cohesion_pull,
    local_density,
    separation_push,
    steer_toward,
    wander_heading,
)

GROUND = settings.GROUND_TOP


def _n(x: float, y: float = GROUND, vx: float = 0.0, facing: int = 1) -> Neighbor:
    """Build a neighbour record for the steering rules under test."""
    return Neighbor(Vector2(x, y), facing, vx)


class _NoReorientRng:
    """random-like stub: applies a fixed drift and never fires a reorientation.

    ``uniform`` returns the configured drift fraction; ``random`` returns 1.0 so
    it is never below ``WANDER_REORIENT_CHANCE * dt``. Lets a test isolate the
    coherent per-frame drift from the occasional larger reorientation."""

    def __init__(self, drift: float) -> None:
        self._drift = drift

    def uniform(self, a: float, b: float) -> float:
        return self._drift

    def random(self) -> float:
        return 1.0


def test_steer_toward_reaches_target_within_cap():
    assert steer_toward(0.0, 5.0, 10.0) == 5.0  # gap within cap -> lands exactly
    assert steer_toward(50.0, 50.0, 10.0) == 50.0  # already there -> no change


def test_steer_toward_is_capped_to_max_delta():
    assert steer_toward(0.0, 100.0, 10.0) == 10.0  # eases, does not snap
    assert steer_toward(0.0, -100.0, 10.0) == -10.0


def test_wander_heading_drifts_coherently_not_rerolled():
    # Max positive drift every frame, no reorientation: the heading must change
    # by at most WANDER_DISPLACE*dt per step (coherent), not jump arbitrarily.
    rng = _NoReorientRng(drift=1.0)
    dt = 1 / 60
    heading = 0.0
    prev = heading
    for _ in range(10):
        heading = wander_heading(heading, dt, rng=rng)
        assert abs(heading - prev) <= settings.WANDER_DISPLACE * dt + 1e-9
        prev = heading
    assert heading > 0.0  # coherent drift accumulates, not random noise


def test_wander_heading_clamped_to_walk_speed():
    rng = _NoReorientRng(drift=1.0)  # drive it hard toward the positive clamp
    heading = 0.0
    for _ in range(1000):
        heading = wander_heading(heading, 1 / 60, rng=rng)
    assert heading <= settings.WALK_SPEED + 1e-9
    assert heading >= -settings.WALK_SPEED - 1e-9


def test_no_neighbors_means_no_push():
    assert separation_push(Vector2(100, GROUND), []) == 0.0


def test_push_is_away_from_a_same_surface_neighbor():
    me = Vector2(100, GROUND)
    push = separation_push(me, [_n(110)])  # neighbor on the right, within radius
    assert push < 0  # pushed left (negative x)

    assert separation_push(me, [_n(90)]) > 0  # neighbor on the left -> pushed right


def test_neighbor_outside_y_band_is_ignored():
    me = Vector2(100, GROUND)
    # Same x-distance, but on a different surface (y differs by > HSEP_Y_BAND).
    far_y = _n(110, GROUND - settings.HSEP_Y_BAND - 1)
    assert separation_push(me, [far_y]) == 0.0


def test_neighbor_beyond_radius_is_ignored():
    me = Vector2(100, GROUND)
    assert separation_push(me, [_n(100 + settings.HSEP_RADIUS + 5)]) == 0.0


def test_separation_ignores_own_record_at_zero_distance():
    # The shared neighbour list includes the agent itself; dist 0 must not push.
    me = Vector2(100, GROUND)
    assert separation_push(me, [_n(100)]) == 0.0


def test_push_is_clamped_to_hsep_push():
    me = Vector2(100, GROUND)
    # A cluster of very-close neighbors on the right would sum past the cap.
    crowd = [_n(101) for _ in range(20)]
    push = separation_push(me, crowd)
    assert -settings.HSEP_PUSH <= push <= settings.HSEP_PUSH


def test_cohesion_pulls_toward_the_local_mean_x():
    me = Vector2(100, GROUND)
    assert cohesion_pull(me, [_n(140), _n(150)]) > 0  # pack to the right -> pull right
    assert cohesion_pull(me, [_n(60), _n(50)]) < 0  # pack to the left -> pull left


def test_cohesion_zero_without_in_range_neighbors():
    me = Vector2(100, GROUND)
    assert cohesion_pull(me, []) == 0.0
    far = _n(100 + settings.CROWD_COH_RADIUS + 10)
    assert cohesion_pull(me, [far]) == 0.0


def test_cohesion_ignores_other_surfaces_and_self():
    me = Vector2(100, GROUND)
    off_band = _n(140, GROUND - settings.HSEP_Y_BAND - 1)
    assert cohesion_pull(me, [off_band]) == 0.0
    assert cohesion_pull(me, [_n(100)]) == 0.0  # own record at dist 0


def test_cohesion_is_clamped_to_walk_speed():
    me = Vector2(100, GROUND)
    # Neighbour at the cohesion radius: offset (80) exceeds WALK_SPEED (60), so
    # the pull saturates rather than overpowering the wander heading.
    n = _n(100 + settings.CROWD_COH_RADIUS)
    assert cohesion_pull(me, [n]) == settings.WALK_SPEED


def test_alignment_matches_mean_neighbor_velocity():
    me = Vector2(100, GROUND)
    movers = [_n(110, vx=40.0), _n(120, vx=20.0)]
    assert alignment_nudge(me, movers) == 30.0  # mean of 40 and 20


def test_alignment_zero_without_in_range_neighbors():
    me = Vector2(100, GROUND)
    assert alignment_nudge(me, []) == 0.0
    far = _n(100 + settings.CROWD_ALI_RADIUS + 5, vx=50.0)
    assert alignment_nudge(me, [far]) == 0.0


def test_alignment_ignores_other_surfaces():
    me = Vector2(100, GROUND)
    off = _n(110, GROUND - settings.HSEP_Y_BAND - 1, vx=50.0)
    assert alignment_nudge(me, [off]) == 0.0


def test_local_density_counts_same_band_in_range_only():
    me = Vector2(100, GROUND)
    crowd = [
        _n(90),  # in band + range
        _n(110),  # in band + range
        _n(100 + settings.CROWD_DENSITY_RADIUS + 1),  # too far
        _n(105, GROUND - settings.HSEP_Y_BAND - 1),  # other surface
    ]
    assert local_density(me, crowd) == 2


def test_local_density_excludes_own_record():
    me = Vector2(100, GROUND)
    assert local_density(me, [_n(100)]) == 0  # dist 0 is self
