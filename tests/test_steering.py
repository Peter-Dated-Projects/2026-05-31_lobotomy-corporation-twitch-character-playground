"""Pure-function tests for the horizontal separation nudge."""

from __future__ import annotations

from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.sim.steering import separation_push


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
