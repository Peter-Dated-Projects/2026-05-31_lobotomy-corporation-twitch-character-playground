---
id: character-def-format
root: conventions
type: convention
status: current
summary: "Characters are defined as frozen CharacterDef dataclasses with CharacterLayer(file, variant) fields; emotion-keyed face layers use dicts; all 10 named characters live in character_defs.py."
related:
  - architecture/character-layer-stack
  - domain/lobcorp-sprite-sheet-catalog
  - domain/lobcorp-10-characters
created: 2026-06-01
updated: 2026-06-01
---

# Character Definition Format

## Data model

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CharacterLayer:
    file: str     # bare filename within the appropriate sprites folder
    variant: int  # extracted sprite index (reading order, 0-based)

@dataclass(frozen=True)
class CharacterDef:
    name: str
    rear_hair:  CharacterLayer
    front_hair: CharacterLayer
    clothes:    str                        # outfit sheet filename (Employee Clothes folder)
    eyes:       dict[str, CharacterLayer]  # keys: default, closed, dead, panic
    eyebrows:   dict[str, CharacterLayer]  # keys: default, battle, panic
    mouth:      dict[str, CharacterLayer]  # keys: default, battle, panic
    glasses:    CharacterLayer | None
    weapon:     CharacterLayer | None
```

## Registry

`twitch_playground/assets/character_defs.py` exposes:
- `CHARACTER_DEFS: dict[str, CharacterDef]` — keyed by `CharacterDef.name`
- `DEFAULT_CHARACTER_ID: str` — `"Standard Agent"`

## Provider assignment for unknown viewers

When a viewer's username doesn't match a named character, `LobCorpProvider` assigns one deterministically by `md5(username) % len(CHARACTER_DEFS)` so each viewer gets a stable, distinct look across sessions.

## No pygame imports in defs

`character_defs.py` is pure data — no pygame, no PIL. Conversion happens in `lobcorp_renderer.py`.
