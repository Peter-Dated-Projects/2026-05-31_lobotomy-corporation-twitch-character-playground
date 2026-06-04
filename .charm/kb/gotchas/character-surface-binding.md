---
id: character-surface-binding
root: gotchas
type: gotcha
status: current
summary: "A Character treats platform is None as airborne (plays the jump clip and falls); to place one ON a surface, its feet pos.y must equal a platform top within 1px so the first update can bind it."
created: 2026-06-01
updated: 2026-06-01
---

`Character.platform` is the single source of truth for "am I standing on a
surface": `None` means **airborne**, which makes `_update_clip` pick the `"jump"`
clip and `_wander` apply gravity. There is no separate "grounded" flag.

A freshly constructed Character has `platform = None`. It only gets bound to a
surface in two ways:

1. **First `update()` frame** — `_surface_at(platforms, pos.x, pos.y)` snaps it
   onto a platform whose `top` is within **1px** of `pos.y`. If you spawn a
   character with feet that are NOT within 1px of a platform top (e.g. a few px
   above the ground), it stays airborne and falls until `landing_surface`
   catches it. Usually harmless, but it means clip/jump state on frame 0 is wrong.
2. **Landing** — `landing_surface` catches it only while **descending** and only
   when a platform top is crossed between the previous and current feet y.

Consequences for the World / Render / Tests tracks:

- When placing a character directly on a surface (spawn on ground, group slots),
  set `pos.y == platform.top` exactly. Group slots already do this
  (`slot.y = leader.platform.top`); spawn must use `feet.y = settings.GROUND_TOP`.
- Don't read `platform is None` as "invalid" — it's a normal mid-hop state.
- Platforms are **one-way**: a rising character passes up through them and only
  lands when falling. So a character can be horizontally inside a platform's span
  yet correctly airborne above or below it.
