---
id: emotion-neighbor-record-lives-in-character
root: gotchas
type: gotcha
status: current
summary: "The shared per-frame neighbour record carrying emotion fields is the NamedTuple Neighbor in sim/character.py, NOT sim/steering.py where the architecture note says it should live; steering's pure rules read it by duck typing."
created: 2026-06-01
updated: 2026-06-01
related:
  - architecture/agent-behavior-model
  - gotchas/shared-neighbor-list-includes-self
---

# Emotion neighbour record lives in character.py, not steering.py

The architecture note (`architecture/agent-behavior-model.md`, plumbing #1) says
to extend the L3 neighbour record in place -- it was originally
`steering.Neighbor` `(pos, facing, vx)`. L5 needed three more fields
`(arousal, valence, expressiveness)` so emotional contagion can reuse the one
shared per-frame scan.

But the L5 ticket's `touches` scope did NOT include `sim/steering.py`. So the
authoritative neighbour record is now the `Neighbor` `NamedTuple` defined in
**`sim/character.py`**, and `World.update` builds *that*. `steering.Neighbor`
still exists (unused by World) but is the old 3-field shape.

Why this is safe: the pure steering helpers (`separation_push`, `cohesion_pull`,
`alignment_nudge`, `local_density`) only ever read `.pos` / `.facing` / `.vx` and
their parameters are duck-typed (`list[Neighbor]` is just an annotation), so the
richer `character.Neighbor` is a drop-in everywhere they're called.

Implications for a future agent:
- Add new shared-scan fields to `character.Neighbor`, not `steering.Neighbor`.
- If steering.py ever comes into scope, the clean move is to consolidate back to
  a single record there and have character import it -- but mind the import
  direction (character imports steering today; world imports character, so the
  record can't live in a module that imports character without a cycle).
- The record still includes the agent's OWN snapshot (distance 0); contagion
  skips it with a `d <= 0.0` guard, mirroring the steering rules'
  [shared-neighbor-list-includes-self](shared-neighbor-list-includes-self.md)
  `0 < dist` test.
