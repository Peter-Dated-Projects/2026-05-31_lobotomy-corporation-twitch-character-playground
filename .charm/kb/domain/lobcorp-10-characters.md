---
id: lobcorp-10-characters
root: domain
type: domain
status: current
summary: "The 10 named playable characters: their outfit file, hair variants, eye/eyebrow/mouth sheet variants, and weapon — all indexed from the extracted sprite reading order."
related:
  - domain/lobcorp-sprite-sheet-catalog
  - conventions/character-def-format
  - architecture/character-layer-stack
created: 2026-06-01
updated: 2026-06-01
---

# The 10 Named Characters

Variant indices are 0-based, extracted in reading order from each sheet. See `sprite-extraction-algorithm` for how reading order is defined.

| # | Name | Clothes file | Front hair (v) | Rear hair (v) | Eyes / v | Eyebrows / v | Mouth / v | Weapon |
|---|---|---|---|---|---|---|---|---|
| 1 | Standard Agent | Agent-1521 | FrontHair v0 (black) | RearHair v0 (black) | Default v0 | EyeBrow_1 v0 | Mouth_1 v0 | Pistol_Set_01 v2 |
| 2 | Officer Chesed | Officer_Chesed-1278 | FrontHair v1 (blonde) | RearHair v1 (blonde) | Default v3 | EyeBrow_1 v3 | Mouth_1 v0 | none |
| 3 | Officer Binah | Officer_Binah-2969 | FrontHair v0 (black) | RearHair v0 (black) | Dead v0 | EyeBrow_Battle_1 v3 | Mouth_1 v0 | none |
| 4 | Officer Geburah | Officer_Geburah-1745 | FrontHair v8 (red) | RearHair v2 (dark) | Default v15 | EyeBrow_Battle_1 v2 | Mouth_Battle_1 v0 | Spear_Set_01 v0 |
| 5 | Officer Netzach | Officer_Netzach-2749 | FrontHair v4 (messy) | RearHair v3 (teal) | Panic v0 | EyeBrow_Panic v0 | Mouth_Panic_1 v0 | none |
| 6 | Officer Hod | Officer_Hod-4136 | FrontHair v6 (long dark) | RearHair v2 (dark) | Default v5 | EyeBrow_1 v4 | Mouth_1 v0 | BowGun_Set_01 v0 |
| 7 | Officer Malkut | Officer_Malkut-1437 | FrontHair v7 (bowl cut) | RearHair v3 (teal) | Default v8 | EyeBrow_1 v5 | Mouth_1 v0 | Rifle_Set_01 v0 |
| 8 | Officer Yesod | Officer_Yesod-4431 | FrontHair v9 (navy) | RearHair v4 (navy strip) | Default v12 | EyeBrow_1 v6 | Mouth_1 v0 | Pistol_Set_01 v0 |
| 9 | Panicked Worker | Agent-1521 | FrontHair v2 (white) | RearHair v0 (black) | Panic v4 | EyeBrow_Panic v2 | Mouth_Panic_1 v1 | Defaultweapon v0 |
| 10 | Battle-Ready Agent | Agent-1521 | FrontHair v11 (teal) | RearHair v3 (teal) | Default v20 | EyeBrow_Battle_1 v1 | Mouth_Battle_1 v1 | Hammer_Set_01 v0 |

## Notes

- Calibrated against the actual `extract_sprites()` counts on the real sheets (2026-06-01); every index above is in-range. Sheet counts measured: Mouth_1 **1** (index 0 only — connected-component extraction merges its glyphs), Mouth_Battle_1 8, Mouth_Panic_1 8; Eye_Default_1 64, Eye_Panic_1 8, Eye_Close_1 6, Eye_Dead_1 4; EyeBrow_1 7, EyeBrow_Battle_1 14, EyeBrow_Panic 15; Credit_FrontHair 18, Credit_RearHair 7; Agent 11, Agent2 6, Officer_* 11 (Yesod 12); weapons Pistol 5, Rifle 2, Hammer 4, Spear 8, BowGun 3, Defaultweapon 1.
- Because Mouth_1 yields only v0, every default-mouth character (Chesed, Hod, Malkut, Yesod) uses Mouth_1 v0 — the earlier v4/v3/v2/v5 references were out of range and fell back to placeholder.
- Battle-Ready Agent's clothes were Agent2 (only 6 variants), but the walk clip indexes clothes limbs up to `3 + 7 = 10`, so it needs an 11+ variant sheet — repointed to Agent-1521. A clothes sheet must always carry >=11 variants.
- Emotion-keyed face dicts default to `"default"` state as fallback if a key is missing.
- KNOWN RENDER ISSUE (separate from index calibration): with calibrated in-range indices all 10 now composite real art (no placeholder fallback), but the result does not yet read as a face. Extracted part sprites are full-resolution (Head ~193x200, Credit_FrontHair ~235x215, Agent body ~66x94) while the composite canvas is only 32x40 (`SPRITE_W` x `SPRITE_H`), and `compose_character` blits each layer centered WITHOUT scaling — so every big layer covers the whole canvas and only a tiny central crop shows. Fixing this needs a per-layer downscale step in the renderer, not a data change here.
- All outfit filenames above are abbreviated — prepend `resources.assets-` suffix as shown in the catalog.
