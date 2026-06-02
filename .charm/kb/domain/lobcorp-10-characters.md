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
| 2 | Officer Chesed | Officer_Chesed-1278 | FrontHair v1 (blonde) | RearHair v1 (blonde) | Default v3 | EyeBrow_1 v3 | Mouth_1 v4 | none |
| 3 | Officer Binah | Officer_Binah-2969 | FrontHair v0 (black) | RearHair v0 (black) | Dead v0 | EyeBrow_Battle_1 v3 | Mouth_1 v0 | none |
| 4 | Officer Geburah | Officer_Geburah-1745 | FrontHair v8 (red) | RearHair v2 (dark) | Default v15 | EyeBrow_Battle_1 v2 | Mouth_Battle_1 v0 | Spear_Set_01 v0 |
| 5 | Officer Netzach | Officer_Netzach-2749 | FrontHair v4 (messy) | RearHair v3 (teal) | Panic v0 | EyeBrow_Panic v0 | Mouth_Panic_1 v0 | none |
| 6 | Officer Hod | Officer_Hod-4136 | FrontHair v6 (long dark) | RearHair v2 (dark) | Default v5 | EyeBrow_1 v4 | Mouth_1 v3 | BowGun_Set_01 v0 |
| 7 | Officer Malkut | Officer_Malkut-1437 | FrontHair v7 (bowl cut) | RearHair v3 (teal) | Default v8 | EyeBrow_1 v5 | Mouth_1 v2 | Rifle_Set_01 v0 |
| 8 | Officer Yesod | Officer_Yesod-4431 | FrontHair v9 (navy) | RearHair v4 (navy strip) | Default v12 | EyeBrow_1 v6 | Mouth_1 v5 | Pistol_Set_01 v0 |
| 9 | Panicked Worker | Agent-1521 | FrontHair v2 (white) | RearHair v0 (black) | Panic v4 | EyeBrow_Panic v2 | Mouth_Panic_1 v1 | Defaultweapon v0 |
| 10 | Battle-Ready Agent | Agent2-1782 | FrontHair v11 (teal) | RearHair v3 (teal) | Default v20 | EyeBrow_Battle_1 v1 | Mouth_Battle_1 v1 | Hammer_Set_01 v0 |

## Notes

- Variant indices may need a one-time visual calibration pass after extraction runs, since the 60px row-grouping tolerance can shift indices on sheets where sprites have unusual vertical spacing.
- Emotion-keyed face dicts default to `"default"` state as fallback if a key is missing.
- All outfit filenames above are abbreviated — prepend `resources.assets-` suffix as shown in the catalog.
