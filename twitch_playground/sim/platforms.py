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
    """Just the full-width ground (platform index 0).

    There are no floating tiers: characters stroll and take low cosmetic hops on a
    single floor. The one-way landing machinery below still applies (a character
    rising from a hop passes nothing and falls back onto the ground)."""
    return [
        Platform(0, settings.SCREEN_W, settings.GROUND_TOP),  # ground (index 0)
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
