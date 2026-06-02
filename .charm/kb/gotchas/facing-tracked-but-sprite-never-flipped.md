---
id: facing-tracked-but-sprite-never-flipped
root: gotchas
type: gotcha
status: current
summary: "Character tracks _facing (-1/1) and flips it at edges/pauses, but Character.surface returns the frame unmodified and scene.py never flips, so every character faces the sheet default direction regardless of travel; the fix is a pygame.transform.flip in the renderer keyed off exposed facing (with a WALK_THRESHOLD deadzone)."
created: 2026-06-01
updated: 2026-06-01
---

`sim/character.py` maintains `self._facing` and updates it (platform edges in
`_apply_horizontal_bounds`, after idle pauses in `_wander`), but the rendering
path ignores it entirely: the `Character.surface` property returns the current
clip frame as-is, and the scene renderer blits it without flipping. Net effect:
characters never visually turn around — they always face the sprite sheet's
default direction even while walking the other way.

Standard fix (split across two tracks, so it is a coordination point):
- Sim track exposes facing as public read-only state (alias `_facing` to
  `facing`, or let the renderer derive it from `sign(velocity.x)`).
- World track flips in `render/scene.py` with
  `pygame.transform.flip(surface, True, False)` when facing is left.
- Add a deadzone (reuse `WALK_THRESHOLD`) so a near-zero `velocity.x` driven only
  by `steering.separation_push` does not flicker the flip every frame.

Related: `settings.MAX_SPEED` is defined but referenced nowhere outside
`settings.py` (movement uses `WALK_SPEED`); it is the natural cap to wire up when
adding acceleration easing. Both points are detailed in
`docs/research/npc-movement-steering.md`.
