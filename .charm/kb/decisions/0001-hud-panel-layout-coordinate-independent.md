---
id: hud-panel-layout-coordinate-independent
root: decisions
type: decision
status: current
summary: "The debug HUD renders fixed top-left/bottom-left panels (roster + command log), not world-space labels over each sprite, so it stays correct across coordinate/scene changes."
created: 2026-06-01
updated: 2026-06-01
---

The contract calls for a "per-character mode/clip label". We render it as a
fixed top-left panel listing `username  MODE/clip[ gN]` per character, plus a
bottom-left rolling command log -- not as text anchored over each sprite in
world space.

Why:
- The sidescroller rebuild changes the coordinate convention (feet/midbottom
  anchoring) and the scene draw. A panel that reads only `world.characters` and
  each character's `mode`/`clip`/`group_id` is immune to those changes; a
  world-space label would have to track sprite anchors and could collide with
  nameplates the scene already draws.
- `render/hud.py` reads sim state defensively via `getattr` (e.g.
  `getattr(mode, "name", ...)`). This was deliberate while T-009 (sim) and
  T-010 (world) were rewriting `character.py`/`world.py` in parallel -- the HUD
  must not crash if an attribute shape shifts mid-rebuild. Keep the defensive
  reads; the render layer should never assume more of the sim than the contract
  guarantees.

Fonts are built once and cached at module level (`_get_fonts`); rebuilding a
SysFont every frame is needless cost. `LOG_MAXLEN` lives in `hud.py` and
`main.py` sizes its command deque from it so the two never drift.
