"""Per-character personality (L4): a deterministic trait struct seeded from the
username, plus the pure utility functions that turn those traits into autonomous
join / leave decisions.

This module is intentionally dependency-free (no pygame, like
``assets.character_defs``): it is pure data + pure scalar math, so it imports
instantly and tests headlessly. ``settings`` is the only import, for the tunable
thresholds. The actual grouping mutation (``_add_to_group`` / ``_remove_from_group``)
lives in ``World``; this module only *scores* the decision.

Determinism
-----------
Traits are derived from ``md5("persona:" + username)``. md5 is chosen over
Python's built-in ``hash()`` (which is salted per-process and unstable across
runs) so a viewer who is solitary today is solitary next week -- the same
stability guarantee ``assets.character_defs.assign_character`` relies on. The
``"persona:"`` salt is deliberately DIFFERENT from the appearance hash so a
character's behaviour is decorrelated from its look; otherwise every viewer who
renders as "Officer Hod" would also act identically.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from twitch_playground import settings

# Salt prefix for the personality digest. Must differ from the appearance hash
# in ``assign_character`` (which hashes the bare username) so traits and looks
# are independent.
_PERSONA_SALT = "persona:"
_WINDOW = 0xFFFF  # 16-bit window; md5 is 128 bits, plenty for three windows


@dataclass(frozen=True)
class Personality:
    """Three continuous personality axes in ``[0, 1]`` (see
    ``docs/research/crowd-following-personality.md`` 1.2).

    - ``sociability``  -- pull toward other characters; sets the join threshold.
    - ``independence`` -- resistance to following the crowd; raises the threshold
      and shortens the stay.
    - ``restlessness`` -- how often the character re-decides / wanders off; also
      multiplies the global jump/idle cadence.
    """

    sociability: float
    independence: float
    restlessness: float


def personality_for(username: str) -> Personality:
    """Deterministically derive a :class:`Personality` from ``username``.

    Three independent 16-bit windows are carved out of one md5 digest -- no
    per-axis hashing needed, and the windows are uncorrelated. The raw uniform
    draws are then *skewed* so the room reads right: the threshold-model insight
    (Granovetter) is that the *distribution shape*, not the mean, decides whether
    crowds form. We make genuine loners a minority and most characters socially
    inclined:

    - ``sociability``  = sqrt(raw)  -> up-skewed: most are mildly-to-strongly social.
    - ``independence`` = raw**2     -> down-skewed: true contrarians are a thin tail,
      so most characters have a low Granovetter threshold and clusters nucleate.
    - ``restlessness`` = raw        -> left uniform; pure cosmetic variety.

    Same ``username`` always yields the same traits, across process restarts.
    """
    digest = hashlib.md5(f"{_PERSONA_SALT}{username}".encode("utf-8")).hexdigest()
    h = int(digest, 16)
    raw_soc = ((h >> 0) & _WINDOW) / _WINDOW
    raw_ind = ((h >> 16) & _WINDOW) / _WINDOW
    raw_rest = ((h >> 32) & _WINDOW) / _WINDOW
    return Personality(
        sociability=raw_soc ** 0.5,
        independence=raw_ind ** 2,
        restlessness=raw_rest,
    )


# --- utility / decision functions -------------------------------------------
# Pure, trait-parameterised scalar math: same world state, different traits ->
# different winning action. Recomputed on a low-frequency decide tick by World.


def join_threshold(persona: Personality) -> int:
    """Granovetter per-character join count ``T = 1 + round(independence * MAX)``.

    A sociable / low-independence character has ``T == 1`` (joins a single other
    character); a solitary character has a high ``T`` (needs a near-mob), and the
    most extreme effectively never auto-joins because no realistic knot clears it.
    """
    return 1 + round(persona.independence * settings.MAX_JOIN_THRESHOLD)


def proximity_curve(distance: float) -> float:
    """Response curve on horizontal distance to the nearest cluster: ``1`` when
    adjacent, ramping linearly to ``0`` at ``JOIN_RADIUS`` and beyond."""
    return max(0.0, 1.0 - distance / settings.JOIN_RADIUS)


def threshold_curve(crowd_size: int, persona: Personality) -> float:
    """Granovetter step: ``0`` until the perceived crowd clears this character's
    join threshold ``T``, then ``1``. The continuous shaping of the join utility
    comes from proximity / sociability; this factor is the hard social gate."""
    return 1.0 if crowd_size >= join_threshold(persona) else 0.0


def join_score(persona: Personality, crowd_size: int, distance: float) -> float:
    """Utility for autonomously joining a nearby cluster (``[0, 1]``).

    ``sociability * proximity_curve(d) * threshold_curve(n) * (1 - independence)``
    -- sociable characters near a knot that clears their threshold score high;
    loners discount the social pull toward zero (``docs/research/
    crowd-following-personality.md`` 2.2).
    """
    return (
        persona.sociability
        * proximity_curve(distance)
        * threshold_curve(crowd_size, persona)
        * (1.0 - persona.independence)
    )


def leave_floor(persona: Personality) -> int:
    """Crowd-size floor for the leave check: ``join_threshold - 1``.

    Strictly below the join threshold ``T`` so the same crowd size that pulled a
    character in does not immediately push them back out -- this gap is the
    dual-threshold dead-band that, with the dwell timer, prevents boundary
    vibration. A sociable character (``T == 1``) gets floor ``0`` and so never
    autonomously leaves; loners get a high floor and peel off readily.
    """
    return join_threshold(persona) - 1


def shrink_curve(crowd_size: int) -> float:
    """Leave pressure from cluster size: high for a small/stale cluster, low for
    a big sticky one. ``1 / max(1, n - 1)`` -> ``1.0`` at ``n == 2``, ``0.5`` at
    ``n == 3``, tapering as the crowd grows."""
    return 1.0 / max(1, crowd_size - 1)


def dwell_curve(time_in_group: float) -> float:
    """Leave pressure from time-in-group: suppressed early in the stay, saturating
    to ``1`` by the ``JOIN_DWELL`` commit window so a fresh joiner is not
    immediately tempted away."""
    return min(1.0, time_in_group / settings.JOIN_DWELL)


def leave_score(persona: Personality, crowd_size: int, time_in_group: float) -> float:
    """Utility for autonomously leaving the current cluster (``[0, 1]``).

    ``independence * restlessness * shrink_curve(n) * dwell_curve(t)`` -- a
    restless contrarian in a small, stale cluster scores high; a content social
    character in a large fresh cluster scores ~0 (``docs/research/
    crowd-following-personality.md`` 2.2).
    """
    return (
        persona.independence
        * persona.restlessness
        * shrink_curve(crowd_size)
        * dwell_curve(time_in_group)
    )
