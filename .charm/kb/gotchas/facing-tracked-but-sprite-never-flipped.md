---
id: facing-tracked-but-sprite-never-flipped
root: gotchas
type: gotcha
status: resolved
summary: "RESOLVED (T-026, L2): Character now exposes a public read-only facing (1=right unflipped pose, -1=left, committed from velocity.x with a WALK_THRESHOLD deadzone) and render/scene.py flips via pygame.transform.flip when facing<0. Kept for history; the bug is fixed -- do not re-report it."
created: 2026-06-01
updated: 2026-06-01
---

**RESOLVED in T-026 (layer L2).** `Character.facing` is now a public read-only
property committed from `velocity.x` with a `WALK_THRESHOLD` deadzone (held below
the threshold so a separation-only nudge cannot strobe it), and
`render/scene.py` draws `pygame.transform.flip(surface, True, False)` when
`facing < 0`. Sign convention recorded in `docs/design/sidescroller-contract.md`:
`facing == 1` is the unflipped sheet pose (right). MAX_SPEED is now wired up as
the velocity cap. The original bug write-up follows for history.

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
