"""Pure-function tests for the horizontal separation nudge."""

from __future__ import annotations

from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.sim.steering import separation_push, steer_toward, wander_heading


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
    assert separation_push(Vector2(100, settings.GROUND_TOP), []) == 0.0


def test_push_is_away_from_a_same_surface_neighbor():
    me = Vector2(100, settings.GROUND_TOP)
    neighbor_on_right = Vector2(110, settings.GROUND_TOP)  # within HSEP_RADIUS
    push = separation_push(me, [neighbor_on_right])
    assert push < 0  # neighbor on the right -> pushed left (negative x)

    neighbor_on_left = Vector2(90, settings.GROUND_TOP)
    assert separation_push(me, [neighbor_on_left]) > 0


def test_neighbor_outside_y_band_is_ignored():
    me = Vector2(100, settings.GROUND_TOP)
    # Same x-distance, but on a different surface (y differs by > HSEP_Y_BAND).
    far_y = Vector2(110, settings.GROUND_TOP - settings.HSEP_Y_BAND - 1)
    assert separation_push(me, [far_y]) == 0.0


def test_neighbor_beyond_radius_is_ignored():
    me = Vector2(100, settings.GROUND_TOP)
    far_x = Vector2(100 + settings.HSEP_RADIUS + 5, settings.GROUND_TOP)
    assert separation_push(me, [far_x]) == 0.0


def test_push_is_clamped_to_hsep_push():
    me = Vector2(100, settings.GROUND_TOP)
    # A cluster of very-close neighbors on the right would sum past the cap.
    crowd = [Vector2(101, settings.GROUND_TOP) for _ in range(20)]
    push = separation_push(me, crowd)
    assert -settings.HSEP_PUSH <= push <= settings.HSEP_PUSH
