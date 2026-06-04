"""Pure-function tests for level geometry and the one-way landing rule.

No display needed -- Platform/landing_surface are plain dataclasses/functions.
"""

from __future__ import annotations

from twitch_playground import settings
from twitch_playground.sim.platforms import Platform, default_level, landing_surface


def test_platform_contains_x_and_center():
    p = Platform(left=100, right=300, top=400)
    assert p.contains_x(100) and p.contains_x(300) and p.contains_x(200)
    assert not p.contains_x(99) and not p.contains_x(301)
    assert p.center_x == 200


def test_default_level_ground_is_full_width_index_0():
    level = default_level()
    ground = level[0]
    assert ground.left == 0
    assert ground.right == settings.SCREEN_W
    assert ground.top == settings.GROUND_TOP


def test_default_level_is_ground_only():
    """The level is just the full-width ground -- no floating tiers."""
    assert len(default_level()) == 1


def test_default_level_platforms_within_screen_bounds():
    level = default_level()
    for p in level:
        assert 0 <= p.left < p.right <= settings.SCREEN_W
        assert 0 <= p.top <= settings.SCREEN_H


def test_landing_none_when_rising():
    # feet_y < prev_feet_y => moving up => pass through everything.
    level = default_level()
    assert landing_surface(level, prev_feet_y=400, feet_y=300, x=480) is None


def test_landing_catches_ground_when_descending_across_its_top():
    level = default_level()
    g = level[0]
    landed = landing_surface(level, prev_feet_y=g.top - 5, feet_y=g.top + 5, x=10)
    assert landed is g


def test_landing_returns_highest_surface_crossed():
    # Three stacked surfaces all under x; a steep descent crosses all of them.
    # The highest (smallest top) must win.
    high = Platform(0, 200, top=100)
    mid = Platform(0, 200, top=200)
    low = Platform(0, 200, top=300)
    level = [low, mid, high]  # order shouldn't matter
    landed = landing_surface(level, prev_feet_y=50, feet_y=350, x=50)
    assert landed is high


def test_landing_none_when_x_off_platform_span():
    p = Platform(left=100, right=200, top=300)
    # Descending across top=300 but at x outside [100, 200].
    assert landing_surface([p], prev_feet_y=290, feet_y=310, x=400) is None


def test_landing_none_when_top_not_between_prev_and_current():
    p = Platform(0, 200, top=300)
    # Descending but the surface is still below us this frame (not yet crossed).
    assert landing_surface([p], prev_feet_y=100, feet_y=250, x=50) is None
