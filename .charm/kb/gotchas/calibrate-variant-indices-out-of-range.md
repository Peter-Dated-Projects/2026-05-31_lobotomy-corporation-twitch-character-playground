---
id: calibrate-variant-indices-out-of-range
root: gotchas
type: gotcha
status: current
summary: "Half the named characters' face/hair variant indices (the `# calibrate` ones in character_defs.py) exceed what the current extraction yields, so they silently render as placeholder art via LobCorpProvider's per-character fallback, not real composites."
related:
  - architecture/character-layer-stack
  - conventions/character-def-format
  - architecture/sprite-extraction-algorithm
created: 2026-06-01
updated: 2026-06-01
---

# `# calibrate` variant indices are out of range -> silent placeholder fallback

The variant indices in `character_defs.py` were transcribed from a reference
table, not measured against the actual connected-component extraction. Many of
the high ones (e.g. `EYE_DEFAULT, 15` / `20`, `FRONT_HAIR, 8`/`9`/`11`) index
past the number of sprites the extractor actually finds on those sheets, so
`SpriteSheetCache.get(...)` raises `IndexError`.

`LobCorpProvider` catches any such failure per character and falls back to
`PlaceholderProvider` art for that character (warning once per session). The app
never crashes -- but the affected characters render as placeholder capsules, not
real composites, which is easy to mistake for "the renderer is broken."

As of the renderer's first cut, with the local asset drop present, the split is:

- **Real composite (5):** Standard Agent, Officer Binah, Officer Geburah,
  Officer Netzach, Panicked Worker.
- **Placeholder fallback (5, IndexError):** Officer Chesed, Officer Hod,
  Officer Malkut, Officer Yesod, Battle-Ready Agent.

These are exactly the entries flagged `# calibrate` on a face or hair layer. The
fix is a one-time calibration pass: extract each sheet, eyeball the variant grid,
and correct the indices in `character_defs.py` (that file is pure data, no
graphics import needed to edit). The renderer needs no change.

Quick way to see the current split without a window:

```
SDL_VIDEODRIVER=dummy <runner> python  # init display, then:
#   for d in CHARACTER_DEFS.values():
#       try: compose_character(d, "default", 0, SpriteSheetCache())
#       except Exception: ... # this character will fall back
```
