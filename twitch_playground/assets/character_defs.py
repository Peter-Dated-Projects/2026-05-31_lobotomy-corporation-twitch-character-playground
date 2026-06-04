"""Pure-data character definitions for the 10 named LobCorp characters.

This module is intentionally dependency-free: no pygame, no PIL, no numpy. It
describes WHICH sprite sheets and WHICH extracted variant index make up each
character; turning those references into actual surfaces is the renderer's job
(lobcorp_renderer.py). Keeping the data layer pure means it imports instantly,
tests headlessly, and can be edited without a graphics stack present.

Filenames here are the FULL sheet names as they exist on disk, including the
"-resources.assets-NNNN.png" suffix (see the sprite-sheet catalog). Variant
indices are 0-based, in the extraction reading order, and have been calibrated
against the actual extract_sprites() counts on the real sheets (2026-06-01), so
every referenced index is guaranteed in-range.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterLayer:
    """One sprite drawn from a sheet at a specific extracted index."""

    file: str     # bare filename within the appropriate sprites folder
    variant: int  # extracted sprite index (reading order, 0-based)


@dataclass(frozen=True)
class CharacterDef:
    """The full layer stack for one named character.

    Face layers (eyes/eyebrows/mouth) are emotion-keyed dicts. Every dict is
    guaranteed to carry a "default" key; the renderer falls back to it when an
    emotion-specific key is missing.
    """

    name: str
    rear_hair: CharacterLayer
    front_hair: CharacterLayer
    clothes: str                          # outfit sheet filename (Employee Clothes folder)
    eyes: dict[str, CharacterLayer]       # keys: default, closed, dead, panic
    eyebrows: dict[str, CharacterLayer]   # keys: default, battle, panic
    mouth: dict[str, CharacterLayer]      # keys: default, battle, panic
    glasses: CharacterLayer | None
    weapon: CharacterLayer | None


# --- Sheet filenames (full, on-disk names) --------------------------------
# Outfits (Employee Clothes and Weapons folder).
AGENT = "Agent-resources.assets-1521.png"
# Agent2 has only 6 extracted variants -- too few to serve as a clothes sheet
# (the walk clip indexes clothes limbs up to 10), so it is not used as an outfit.
AGENT2 = "Agent2-resources.assets-1782.png"
OFFICER_BINAH = "Officer_Binah-resources.assets-2969.png"
OFFICER_CHESED = "Officer_Chesed-resources.assets-1278.png"
OFFICER_GEBURAH = "Officer_Geburah-resources.assets-1745.png"
OFFICER_NETZACH = "Officer_Netzach-resources.assets-2749.png"
OFFICER_HOD = "Officer_Hod-resources.assets-4136.png"
OFFICER_MALKUT = "Officer_Malkut-resources.assets-1437.png"
OFFICER_YESOD = "Officer_Yesod-resources.assets-4431.png"

# Weapons.
PISTOL = "Pistol_Set_01-resources.assets-3864.png"
RIFLE = "Rifle_Set_01-resources.assets-2108.png"
HAMMER = "Hammer_Set_01-resources.assets-4762.png"
SPEAR = "Spear_Set_01-resources.assets-2291.png"
BOWGUN = "BowGun_Set_01-resources.assets-2394.png"
DEFAULT_WEAPON = "Defaultweapon-resources.assets-2464.png"

# Hair (Employee Parts folder).
FRONT_HAIR = "Credit_FrontHair-resources.assets-4153.png"
REAR_HAIR = "Credit_RearHair-resources.assets-1862.png"

# Face component sheets, by emotion.
EYE_DEFAULT = "Eye_Default_1-resources.assets-4222.png"
EYE_PANIC = "Eye_Panic_1-resources.assets-3706.png"
EYE_CLOSE = "Eye_Close_1-resources.assets-1195.png"
EYE_DEAD = "Eye_Dead_1-resources.assets-3449.png"

BROW_DEFAULT = "EyeBrow_1-resources.assets-2669.png"
BROW_BATTLE = "EyeBrow_Battle_1-resources.assets-3390.png"
BROW_PANIC = "EyeBrow_Panic-resources.assets-2104.png"

MOUTH_DEFAULT = "Mouth_1-resources.assets-3753.png"
MOUTH_BATTLE = "Mouth_Battle_1-resources.assets-4056.png"
MOUTH_PANIC = "Mouth_Panic_1-resources.assets-3018.png"


# --- Face-dict builders ---------------------------------------------------
# The table gives each character a single resting expression. That goes in the
# "default" key; the remaining emotion keys reuse the closest matching sheet so
# every dict is complete. Variant 0 is a safe stand-in until a character needs a
# bespoke emotion frame.

def _eyes(default: CharacterLayer, *, closed: int = 0, dead: int = 0, panic: int = 0) -> dict[str, CharacterLayer]:
    return {
        "default": default,
        "closed": CharacterLayer(EYE_CLOSE, closed),
        "dead": CharacterLayer(EYE_DEAD, dead),
        "panic": CharacterLayer(EYE_PANIC, panic),
    }


def _brows(default: CharacterLayer, *, battle: int = 0, panic: int = 0) -> dict[str, CharacterLayer]:
    return {
        "default": default,
        "battle": CharacterLayer(BROW_BATTLE, battle),
        "panic": CharacterLayer(BROW_PANIC, panic),
    }


def _mouth(default: CharacterLayer, *, battle: int = 0, panic: int = 0) -> dict[str, CharacterLayer]:
    return {
        "default": default,
        "battle": CharacterLayer(MOUTH_BATTLE, battle),
        "panic": CharacterLayer(MOUTH_PANIC, panic),
    }


# --- The 10 named characters ----------------------------------------------
# Variant indices have been calibrated against the actual extraction counts on
# the real sheets (2026-06-01); every index below is in-range for its sheet.
# Note Mouth_1 yields only a single sprite (index 0) -- connected-component
# extraction merges its glyphs -- so every default-mouth reference is v0.

_DEFS: list[CharacterDef] = [
    CharacterDef(
        name="Standard Agent",
        rear_hair=CharacterLayer(REAR_HAIR, 0),
        front_hair=CharacterLayer(FRONT_HAIR, 0),
        clothes=AGENT,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 0)),
        eyebrows=_brows(CharacterLayer(BROW_DEFAULT, 0)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),
        glasses=None,
        weapon=CharacterLayer(PISTOL, 2),
    ),
    CharacterDef(
        name="Officer Chesed",
        rear_hair=CharacterLayer(REAR_HAIR, 1),
        front_hair=CharacterLayer(FRONT_HAIR, 1),
        clothes=OFFICER_CHESED,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 3)),
        eyebrows=_brows(CharacterLayer(BROW_DEFAULT, 3)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),  # Mouth_1 yields only v0
        glasses=None,
        weapon=None,
    ),
    CharacterDef(
        name="Officer Binah",
        rear_hair=CharacterLayer(REAR_HAIR, 0),
        front_hair=CharacterLayer(FRONT_HAIR, 0),
        clothes=OFFICER_BINAH,
        # Binah's resting face is a dead/dull stare and a battle brow.
        eyes=_eyes(CharacterLayer(EYE_DEAD, 0)),
        eyebrows=_brows(CharacterLayer(BROW_BATTLE, 3)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),
        glasses=None,
        weapon=None,
    ),
    CharacterDef(
        name="Officer Geburah",
        rear_hair=CharacterLayer(REAR_HAIR, 2),
        front_hair=CharacterLayer(FRONT_HAIR, 8),
        clothes=OFFICER_GEBURAH,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 15)),
        eyebrows=_brows(CharacterLayer(BROW_BATTLE, 2)),
        mouth=_mouth(CharacterLayer(MOUTH_BATTLE, 0)),
        glasses=None,
        weapon=CharacterLayer(SPEAR, 0),
    ),
    CharacterDef(
        name="Officer Netzach",
        rear_hair=CharacterLayer(REAR_HAIR, 3),
        front_hair=CharacterLayer(FRONT_HAIR, 4),
        clothes=OFFICER_NETZACH,
        # Netzach is perpetually weary/panicked.
        eyes=_eyes(CharacterLayer(EYE_PANIC, 0)),
        eyebrows=_brows(CharacterLayer(BROW_PANIC, 0)),
        mouth=_mouth(CharacterLayer(MOUTH_PANIC, 0)),
        glasses=None,
        weapon=None,
    ),
    CharacterDef(
        name="Officer Hod",
        rear_hair=CharacterLayer(REAR_HAIR, 2),
        front_hair=CharacterLayer(FRONT_HAIR, 6),
        clothes=OFFICER_HOD,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 5)),
        eyebrows=_brows(CharacterLayer(BROW_DEFAULT, 4)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),  # Mouth_1 yields only v0
        glasses=None,
        weapon=CharacterLayer(BOWGUN, 0),
    ),
    CharacterDef(
        name="Officer Malkut",
        rear_hair=CharacterLayer(REAR_HAIR, 3),
        front_hair=CharacterLayer(FRONT_HAIR, 7),
        clothes=OFFICER_MALKUT,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 8)),
        eyebrows=_brows(CharacterLayer(BROW_DEFAULT, 5)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),  # Mouth_1 yields only v0
        glasses=None,
        weapon=CharacterLayer(RIFLE, 0),
    ),
    CharacterDef(
        name="Officer Yesod",
        rear_hair=CharacterLayer(REAR_HAIR, 4),
        front_hair=CharacterLayer(FRONT_HAIR, 9),
        clothes=OFFICER_YESOD,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 12)),
        eyebrows=_brows(CharacterLayer(BROW_DEFAULT, 6)),
        mouth=_mouth(CharacterLayer(MOUTH_DEFAULT, 0)),  # Mouth_1 yields only v0
        glasses=None,
        weapon=CharacterLayer(PISTOL, 0),
    ),
    CharacterDef(
        name="Panicked Worker",
        rear_hair=CharacterLayer(REAR_HAIR, 0),
        front_hair=CharacterLayer(FRONT_HAIR, 2),
        clothes=AGENT,
        eyes=_eyes(CharacterLayer(EYE_PANIC, 4)),
        eyebrows=_brows(CharacterLayer(BROW_PANIC, 2)),
        mouth=_mouth(CharacterLayer(MOUTH_PANIC, 1)),
        glasses=None,
        weapon=CharacterLayer(DEFAULT_WEAPON, 0),
    ),
    CharacterDef(
        name="Battle-Ready Agent",
        rear_hair=CharacterLayer(REAR_HAIR, 3),
        front_hair=CharacterLayer(FRONT_HAIR, 11),
        # Agent2 packs only 6 variants, but the walk clip indexes clothes limbs
        # up to 3 + 7 = 10, so it needs an 11+ variant sheet -- use Agent.
        clothes=AGENT,
        eyes=_eyes(CharacterLayer(EYE_DEFAULT, 20)),
        eyebrows=_brows(CharacterLayer(BROW_BATTLE, 1)),
        mouth=_mouth(CharacterLayer(MOUTH_BATTLE, 1)),
        glasses=None,
        weapon=CharacterLayer(HAMMER, 0),
    ),
]

CHARACTER_DEFS: dict[str, CharacterDef] = {d.name: d for d in _DEFS}

DEFAULT_CHARACTER_ID: str = "Standard Agent"


def assign_character(username: str) -> str:
    """Deterministically map an arbitrary viewer name to a character key.

    Stability matters: a viewer should look the same every session and across
    process restarts, so we cannot use Python's salted ``hash()``. We hash the
    username with md5 (stable across runs), reduce it modulo the character
    count, and index into a *sorted* list of keys. Sorting the keys makes the
    mapping independent of dict insertion order, so adding a character only
    shifts assignments deterministically rather than scrambling them randomly.

    The result is always a valid key in ``CHARACTER_DEFS``.
    """

    keys = sorted(CHARACTER_DEFS)
    digest = hashlib.md5(username.encode("utf-8")).hexdigest()
    return keys[int(digest, 16) % len(keys)]
