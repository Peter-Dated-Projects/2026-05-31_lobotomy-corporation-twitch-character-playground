"""Side-view level geometry. The ground is just platform index 0 (full width);
floating platforms sit above it. Platforms are one-way: a character passes up
through them while rising and lands on top while falling.
"""

from __future__ import annotations

from dataclasses import dataclass

from twitch_playground import settings


@dataclass(frozen=True)
class Platform:
    left: float
    right: float
    top: float  # y of the standing surface (smaller = higher on screen)

    def contains_x(self, x: float) -> bool:
        return self.left <= x <= self.right

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2


def default_level() -> list[Platform]:
    """Full-width ground plus a single reachable floating tier.

    The stage is wide and short (1920x200), so there is only room for ONE tier
    above the ground -- rendered as two long slabs flanking a central gap to use
    the width. Its height is one jump above the ground: the 70px gap sits inside
    the ~96px jump apex (see settings.JUMP_SPEED / GRAVITY), so it is reachable in
    a single hop, and feet at GROUND_TOP-70 leave the sprite + nameplate clear of
    the top of the screen."""
    w = settings.SCREEN_W
    tier = settings.GROUND_TOP - 70  # one jump up from the ground
    return [
        Platform(0, w, settings.GROUND_TOP),  # ground (index 0)
        Platform(300, 760, tier),             # left floating slab
        Platform(w - 760, w - 300, tier),     # right floating slab
    ]


def landing_surface(
    platforms: list[Platform], prev_feet_y: float, feet_y: float, x: float
) -> Platform | None:
    """The platform a descending character lands on this frame, if any.

    Returns the highest surface whose top was crossed from above between the
    previous and current feet position at horizontal position x.
    """
    if feet_y < prev_feet_y:  # rising -> pass through everything
        return None
    best: Platform | None = None
    for p in platforms:
        if p.contains_x(x) and prev_feet_y <= p.top <= feet_y:
            if best is None or p.top < best.top:
                best = p
    return best
