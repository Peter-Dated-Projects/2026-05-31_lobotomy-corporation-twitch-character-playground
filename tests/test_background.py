"""Pure-geometry tests for the backdrop's drifting triangles.

The motion model (rise / spin / off-top detection / wrap-respawn) is plain math
on a dataclass, so it is tested without touching a pygame surface. A seeded RNG
makes _spawn deterministic. The conftest display fixture means constructing a
Background (which loads + cover-fits the image) is also safe headless, but these
tests deliberately stay on the geometry so they never depend on the art asset.
"""

from __future__ import annotations

import random

from twitch_playground.render.background import (
    TRIANGLE_COUNT,
    Background,
    Triangle,
)


def _tri(**kw) -> Triangle:
    base = dict(x=10.0, y=100.0, size=20.0, angle=0.0, spin=0.0, rise=0.0)
    base.update(kw)
    return Triangle(**base)


def test_step_rises_and_spins():
    tri = _tri(y=100.0, rise=10.0, spin=90.0, angle=0.0)
    tri.step(0.5)
    assert tri.y == 95.0  # rose 10 px/s * 0.5s
    assert tri.angle == 45.0  # spun 90 deg/s * 0.5s


def test_step_angle_wraps_mod_360():
    tri = _tri(angle=350.0, spin=40.0)
    tri.step(1.0)  # 350 + 40 = 390 -> 30
    assert tri.angle == 30.0


def test_negative_spin_wraps_into_range():
    tri = _tri(angle=10.0, spin=-40.0)
    tri.step(1.0)  # 10 - 40 = -30 -> 330
    assert tri.angle == 330.0


def test_is_above_top_is_conservative():
    # Anchor still on screen -> not yet above the top.
    assert not _tri(y=0.0, size=20.0).is_above_top()
    # Anchor above y=0 but the body still pokes below it -> not yet gone.
    assert not _tri(y=-10.0, size=20.0).is_above_top()
    # Whole body (anchor + size) clears the top edge.
    assert _tri(y=-21.0, size=20.0).is_above_top()


def test_update_respawns_triangle_that_rose_off_top():
    bg = Background((1920, 200), rng=random.Random(0), count=1)
    tri = bg.triangles[0]
    # Force it just past the top so the next update wraps it.
    tri.y = -(tri.size + 1)
    tri.rise = 0.0
    assert tri.is_above_top()
    bg.update(0.016)
    replacement = bg.triangles[0]
    assert replacement is not tri  # a fresh triangle took its slot
    # Respawns enter from just below the bottom edge and rise back in.
    assert replacement.y >= bg.height


def test_update_leaves_on_screen_triangle_in_place():
    bg = Background((1920, 200), rng=random.Random(1), count=1)
    tri = bg.triangles[0]
    tri.y = 100.0
    tri.rise = 5.0
    bg.update(0.1)
    assert bg.triangles[0] is tri  # same object, just advanced
    assert tri.y == 99.5


def test_initial_field_is_populated_within_bounds():
    bg = Background((1920, 200), rng=random.Random(2))
    assert len(bg.triangles) == TRIANGLE_COUNT
    for tri in bg.triangles:
        assert 0 <= tri.x <= bg.width
        assert 0 <= tri.y <= bg.height  # initial spawns scatter across the stage
        assert 0 <= tri.angle < 360
