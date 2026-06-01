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
    """Ground plus a symmetric set of reachable floating platforms.

    Heights are tuned so each tier is within one jump of the tier below
    (see settings.JUMP_SPEED / GRAVITY)."""
    w = settings.SCREEN_W
    return [
        Platform(0, w, settings.GROUND_TOP),          # ground (index 0)
        Platform(130, 330, settings.GROUND_TOP - 95),  # left
        Platform(w - 330, w - 130, settings.GROUND_TOP - 95),  # right
        Platform(w / 2 - 90, w / 2 + 90, settings.GROUND_TOP - 185),  # center high
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
