---
id: 0004-layered-agent-behavior
root: decisions
type: decision
status: current
summary: "Adopt a five-layer agent-behavior design — boids-lite ported to 1D-per-surface, brute-force O(N^2) neighbors at N=100, utility+threshold+hysteresis autonomy over a hard FSM, valence/arousal emotion, and appearance-decorrelated md5 trait seeding — over the heavier textbook alternatives."
related:
  - architecture/agent-behavior-model
  - domain/agent-behavior-glossary
  - decisions/0003-per-layer-scale-on-4x-work-canvas
created: 2026-06-01
updated: 2026-06-01
---

# ADR 0004 — Layered Agent Behavior

## Context

Characters currently move robotically: coin-flip direction changes, bang-bang
velocity, a single separation rule, command-only grouping, no emotion, and a
sprite that never faces its travel direction. Four research briefs surveyed the
options for fixing this (steering, crowd simulation, personality/following,
emotion models — under `docs/research/`). This ADR records the design choices
that resolve those briefs into one coherent, ship-scoped plan. The full
implementation map is in
[agent-behavior-model](../architecture/agent-behavior-model.md).

> Numbering note: the literal ticket touch named this `0003-layered-agent-behavior`,
> but `0003` was already taken by
> [per-layer-scale-on-4x-work-canvas](0003-per-layer-scale-on-4x-work-canvas.md);
> it was filed as `0004` to keep ADR prefixes unique.

## Decisions

### 1. Boids-lite ported to 1D-per-surface, not literal 2D SFM/boids

Adopt Reynolds' three local rules (separation, cohesion, alignment) but implement
them as **horizontal, same-surface** scalar nudges, matching the existing
`separation_push` shape — not as 2D vector boids or a full Social Force Model.
Our agents are pinned to platform surfaces and move almost entirely on x; vertical
is gravity/jump owned by the Character. Porting the *ideas* (weighted blend of
local rules, density response) keeps the math and any future spatial acceleration
1D and dramatically simpler.

- **Alternatives considered:** literal 2D boids (wrong motion model — agents
  aren't free-floating); full SFM with continuous exponential repulsion + obstacle
  forces (more faithful to pedestrians, but heavier than a side-scroller needs;
  we keep the *idea* of density-driven slowdown without the differential-equation
  machinery).

### 2. Brute-force O(N^2) neighbor scan kept at N=100; spatial grid deferred

Keep the existing all-pairs neighbor scan. At `MAX_CHARACTERS = 100` and
`FPS = 12` (~83ms/frame budget) that is ~10k cheap comparisons/frame — trivial.
The one discipline adopted now: compute **one** filtered neighbor record list per
agent per frame and feed all rules (separation/cohesion/alignment/density/
contagion) from it, rather than a scan per rule.

- **Deferral trigger:** add a 1D horizontal bucket grid (bucket by
  `floor(pos.x / cell)` per surface-band) **only if** profiling shows the neighbor
  loop dominating, or `MAX_CHARACTERS` is raised well past 100. If a profile flags
  it before N grows, vectorize with numpy first — a grid is the last resort.
  (`docs/research/crowd-awareness-simulation.md` 2.5, 3.)

### 3. Utility + Granovetter threshold + hysteresis for autonomy, not a new FSM

Autonomous join/leave is added as **utility scores with a per-character threshold
and hysteresis**, layered onto the existing `WANDER`/`GROUPED`/`EMOTING` FSM with
no new mode and no rewrite. A low-frequency decide-timer runs a join check in
WANDER and a leave check in GROUPED, routing through the existing grouping
machinery.

- **Why not a hard FSM with explicit follow/solo states:** the trait variation
  (who joins, when) is the whole point, and that lives naturally in scoring
  weights, not in branching states. Utility scoring keeps the logic shared and the
  per-agent parameters varied.
- **Hysteresis is non-negotiable** (dual enter/leave thresholds + dwell timer), or
  characters on a crowd-size boundary oscillate every frame.
- **Chat commands stay authoritative** via a manual-hold timer that suppresses the
  autonomous check after a viewer command.
  (`docs/research/crowd-following-personality.md` 1.1, 1.3-1.4, 2.2-2.3.)

### 4. Valence/arousal emotion — drop PAD dominance, drop full OCC

Represent emotion as **two continuous floats** (valence, arousal) per character,
decaying exponentially toward neutral, spread by proximity-weighted contagion, and
quantized to the three existing faces (`default`/`battle`/`panic`) with hysteresis.

- **Drop the dominance axis** of PAD: valence+arousal cover faces and movement;
  dominance only earns its keep for social-hierarchy NPCs we don't have.
- **Drop full OCC appraisal:** chat commands *are* the appraised events, so we
  apply impulses directly without goals/standards machinery.
- **Mood (slow integral) deferred** to a later iteration; a single decaying
  emotion layer is enough to demo.
  (`docs/research/npc-emotion-models.md` 1, 2.1, 2.6.)

### 5. Deterministic md5 trait seeding, decorrelated from appearance

Seed per-character traits (sociability/independence/restlessness and
susceptibility/expressiveness) from `md5(username)`, reusing the exact pattern in
`assign_character` (md5 chosen over Python's salted `hash()` because the latter is
not stable across runs). **Salt the persona digest differently** (e.g. prefix
`"persona:"`) so traits are decorrelated from the appearance bucket — otherwise
every look-alike behaves identically and the room reads as cloned. Carve
independent byte-windows from one digest for multiple uncorrelated [0,1] axes.
(`docs/research/crowd-following-personality.md` 1.5, 2.1.)

### 6. Sprite-flip facing

Render facing by `pygame.transform.flip(surface, True, False)` when facing is
negative (engine flip flag equivalent), guarded by a `WALK_THRESHOLD` deadzone —
rather than maintaining separate left/right sprite sets. Cheapest high-impact
visual fix; see
[facing-tracked-but-sprite-never-flipped](../gotchas/facing-tracked-but-sprite-never-flipped.md).

## Consequences

- One structural change ripples through all layers: `World.update` passes neighbor
  **records** `(pos, facing, arousal, valence, expressiveness)`, and
  `Character.update`'s signature widens from `neighbor_positions` to `neighbors`.
- The renderer must pre-render three emotion variants per clip (~3x sprite memory),
  a change to the provider/`SpriteSet`.
- All tunables land as named `settings.py` constants (mirroring `HSEP_*` /
  `LAYER_*`), never inline — the liveliness is in the weights, so they must be
  tunable by eye.
- Tests that wait for grouped arrival must keep generous frame budgets — arrive
  easing lengthens the tail
  ([grouped-walk-to-slot-time-is-unbounded](../gotchas/grouped-walk-to-slot-time-is-unbounded.md)).
