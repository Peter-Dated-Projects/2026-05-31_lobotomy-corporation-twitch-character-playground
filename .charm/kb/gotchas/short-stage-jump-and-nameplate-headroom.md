---
id: short-stage-jump-and-nameplate-headroom
root: gotchas
type: gotcha
status: current
summary: "On the 200px-tall stage two height budgets bind any level edit: jump apex (=JUMP_SPEED^2/2GRAVITY, ~96px) must exceed every tier gap, and a floating tier top must leave SPRITE_H+nameplate (~66px) above feet or the standing nameplate clips off the top."
created: 2026-06-01
updated: 2026-06-01
---

The stage is wide and short (SCREEN_W=1920, SCREEN_H=200). On a 200px-tall window
two vertical budgets fight each other, and any change to `default_level()` or the
jump physics has to satisfy both at once:

1. Reachability (the contract invariant). Jump apex = `JUMP_SPEED^2 / (2*GRAVITY)`.
   At the current tune (JUMP_SPEED=480, GRAVITY=1200) that is ~96px. Every floating
   tier's gap above the surface below it MUST be <= apex or it is unreachable.
   JUMP_SPEED was lowered from 580 (apex ~140px) for exactly this reason: a 140px
   arc on a 200px stage flings a character nearly off the top.

2. Nameplate headroom. Sprites are feet-anchored (render/scene.py blits midbottom
   at pos; the nameplate sits just above the sprite top). A character STANDING on a
   tier has its feet at the tier top, so it needs roughly
   `SPRITE_H (40) + small gap + nameplate band (~font 14 -> ~24px)` ≈ 66px of clear
   space above the feet. A floating tier whose `top` is below ~66px will clip the
   nameplate (and sprite) off the top of the screen even while standing still.

Net effect: there is only room for ONE floating tier on this stage. It lives at
`GROUND_TOP - 70` (GROUND_TOP = SCREEN_H - 40 = 160, so tier top = 90): gap 70 < apex
96 (reachable, ~26px margin), and 90 > 66 (nameplate clears the top). Rendered as two
long slabs flanking a central gap to use the 1920 width. If you raise the tier, re-check
reachability; if you lower it, re-check nameplate clearance. `tests/test_platforms.py`
asserts both invariants from the live settings, so a bad retune fails there rather than
silently looking wrong on screen.
