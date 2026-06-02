---
id: lobcorp-sprite-set-shared-across-usernames
root: gotchas
type: gotcha
status: current
summary: "LobCorpProvider keys its SpriteSet cache by resolved CharacterDef name, so many viewer usernames share ONE SpriteSet object; this is only safe because SpriteSets are immutable and all per-character runtime state lives on Character -- never add mutable state to SpriteSet or mutate its frame lists in place."
created: 2026-06-01
updated: 2026-06-01
---

Since T-031, `LobCorpProvider.get_sprite_set` resolves `character_id` (a viewer
username) to a `CharacterDef` first and caches the built `SpriteSet` under
`char_def.name`, not under the raw username. There are only ~10 distinct
character looks, so two usernames that `assign_character` maps to the same def
get the **same `SpriteSet` object back** (identity, not a copy). This keeps cache
memory flat at ~10 entries regardless of viewer count (each SpriteSet is large:
3 emotion faces x 4 clips of composited frames).

The footgun: this sharing is correct ONLY because a `SpriteSet` is an immutable
container of frame surfaces, and every piece of mutable per-character runtime
state (current emotion, animation frame index, facing) lives on the `Character`
instance, not the `SpriteSet`. If you ever:

- add a mutable field to `SpriteSet` that is meant to be per-character, or
- mutate a frame `Surface` in place (e.g. blit onto a cached frame),

you will silently corrupt the look of every viewer sharing that character. The
fix in that case is to copy-on-read or re-key the cache per username -- but
prefer keeping `SpriteSet` immutable.

The placeholder fallback path (composite failure -> `PlaceholderProvider`) is
also keyed by the resolved name, so the fallback cache is bounded the same way.
Related: [[calibrate-variant-indices-out-of-range]] (the per-character fallback
this relies on).
