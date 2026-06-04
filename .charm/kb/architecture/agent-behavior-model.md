---
id: agent-behavior-model
root: architecture
type: architecture
status: current
summary: "The five-layer agent-behavior design (steering core, velocity facing, crowd awareness, seeded personality, emotion) that builds on one shared per-frame neighbor scan and one widened World.update signature."
related:
  - decisions/0004-layered-agent-behavior
  - domain/agent-behavior-glossary
  - architecture/character-layer-stack
  - gotchas/facing-tracked-but-sprite-never-flipped
  - gotchas/grouped-walk-to-slot-time-is-unbounded
created: 2026-06-01
updated: 2026-06-01
---

# Agent Behavior Model

The plan for evolving characters from "move correctly" to "feel alive." It is a
**stack of five layers**, each additive on the one below, designed so an engineer
can scope a ticket per layer. The design synthesizes four research briefs (cited
inline); read those for theory and source links. This note is the implementation
map.

Today's baseline (see `twitch_playground/sim/character.py`,
`sim/steering.py`, `sim/world.py`):

- A `Mode` FSM: `WANDER` (autonomous), `GROUPED` (cluster), `EMOTING` (one-shot).
- Wander = walk in a straight line at `_facing * WALK_SPEED` until a wall/edge,
  flipping `_facing` on bounds and after idle pauses (`random.choice((-1, 1))`).
- One steering rule: `steering.separation_push` (horizontal, same-surface).
- Grouping is **command-only** (`!follow`); the AI never clusters on its own.
- `World.update` builds `positions = [c.pos for ...]` once and passes the bare
  position list to every `Character.update`.

## The two cross-cutting plumbing changes every layer leans on

These are called out first because they are shared infrastructure, not the work
of any single layer — get them in early and the rest is additive.

1. **`World.update` must pass lightweight neighbor RECORDS, not bare positions.**
   Today it passes `list[Vector2]`. Layers 3-5 need each neighbor's heading and
   emotion, so build **one** record per character per frame carrying
   `(pos, facing/velocity_x, arousal, valence, expressiveness)` and hand the same
   list to every consumer (separation, cohesion, alignment, density, contagion).
   `Character.update`'s signature widens from `neighbor_positions` to `neighbors`
   accordingly. This is the single structural change; everything else is additive
   pure-function steering + scalar state. Compute the neighbor filter **once per
   agent** and feed all rules from it — do not write a separate scan per rule (the
   crowd brief reports ~60% of per-agent update cost comes from re-querying;
   `docs/research/crowd-awareness-simulation.md` 2.4-2.5, 3).

2. **The renderer must hold three emotion face variants per clip.** The
   `SpriteSet` clips are currently pre-rendered at the resting `"default"` emotion
   only, even though `compose_character(emotion=...)` accepts
   `default`/`battle`/`panic` (see [character-layer-stack](character-layer-stack.md)).
   L5 needs all three. Recommended: pre-render all three variants per clip at load
   time so the hot path stays a dict lookup + blit (no per-frame compositing);
   ~3x sprite memory, fine at a few dozen characters
   (`docs/research/npc-emotion-models.md` 2.4).

## L1 — Steering core (`steering.py`, `character.py`, `settings.py`)

Replace bang-bang velocity and coin-flip direction with Reynolds-style steering
(`docs/research/npc-movement-steering.md` 1, 2B-2D):

- **Steering = desired - current**, with two separate caps: `MAX_SPEED` (velocity
  magnitude; the constant already exists in `settings.py` but is currently unused)
  and a new `MAX_FORCE`/`WALK_ACCEL` (how sharply it can change). Ease toward the
  desired velocity instead of assigning `velocity.x` directly — starts/stops read
  as weight. Tune ramp to `WALK_SPEED` in ~0.2-0.4s.
- **Coherent 1D wander heading**: a persistent `_wander_heading` that drifts by a
  small random delta each frame (`dt`-scaled) plus occasional larger reorients,
  clamped to `±WALK_SPEED`. This replaces `random.choice((-1, 1))`; edge/wall
  turnarounds flip the *heading*, not a hard `_facing` reroll.
- **Arrive slowdown** for `GROUPED` followers: inside a `GROUP_SLOW_RADIUS` scale
  desired speed linearly to 0, keeping the existing `GROUP_ARRIVE_RADIUS` snap as
  the final settle (replaces full-speed-then-snap in `_move_toward_slot`). Note
  arrival easing lengthens the tail — see
  [grouped-walk-to-slot-time-is-unbounded](../gotchas/grouped-walk-to-slot-time-is-unbounded.md).
- Make the `velocity.x *= 0.6` emote decay `dt`-based (it is currently frame-rate
  dependent). Position integration stays continuous `dt` even at 12 fps, so easing
  reads smoothly despite the low animation rate.

## L2 — Velocity-based facing + sprite flip (`character.py` expose, `render/scene.py` consume)

The current bug: `Character` tracks `_facing` and flips it, but the renderer never
flips the sprite, so everyone faces the sheet default
([facing-tracked-but-sprite-never-flipped](../gotchas/facing-tracked-but-sprite-never-flipped.md)).
Fix: expose facing as public read-only state (or derive from `sign(velocity.x)`),
and in the scene renderer do `pygame.transform.flip(surface, True, False)` when
facing < 0. Guard with a `WALK_THRESHOLD` deadzone/hysteresis so a near-idle
character nudged only by `separation_push` doesn't flicker. Ownership crosses
tracks: Sim exposes `facing`, the World/render track consumes it
(`docs/research/npc-movement-steering.md` 2A).

## L3 — Crowd awareness (`steering.py`, `character.py`, `settings.py`)

Add the other two Reynolds rules beside the existing separation, all horizontal /
same-surface, all fed from the ONE shared neighbor scan
(`docs/research/crowd-awareness-simulation.md` 2.1-2.2):

- **cohesion_pull** — nudge toward the mean x of same-band neighbors within a
  (larger) cohesion radius; pulls stragglers back to the pack.
- **alignment_nudge** — nudge toward the mean heading of same-band neighbors;
  needs neighbor facing/velocity (the L-shared record, see plumbing #1).
- **local_density** — same-band neighbor count, free from the same scan. Use it to
  slow down in crowds, suppress hops when boxed in, and bias idle-pausing up.

Final crowd force is a **weighted blend**, separation-dominant, clamped to a max
nudge:
`crowd = W_SEP*sep + W_COH*coh + W_ALI*ali`. New `settings.py` knobs mirror the
existing `HSEP_*` block (`CROWD_SEP_WEIGHT`, `CROWD_COH_WEIGHT`, `CROWD_ALI_WEIGHT`,
`CROWD_COH_RADIUS`, `CROWD_ALI_RADIUS`, `CROWD_MAX_NUDGE`, density knobs).
Liveliness lives in the weights, not in more rules — expect to tune by eye.

## L4 — Seeded personality (`character.py` / assets layer, `settings.py`)

Give each username a deterministic trait struct so some characters gravitate to
crowds and others stay solitary, repeatably across restarts
(`docs/research/crowd-following-personality.md` 1, 2):

- **Three [0,1] traits**: `sociability`, `independence`, `restlessness`, carved
  from independent byte-windows of one md5 digest. **Salt the persona hash
  differently than `assign_character`** (e.g. prefix `"persona:"`) so behavior is
  decorrelated from appearance — otherwise every look-alike acts identically.
  Skew the draw (e.g. square it) so loners are a minority; the threshold-model
  insight is that the distribution shape, not the mean, decides whether crowds
  form.
- **Autonomous join/leave** via utility scores, layered onto the existing FSM with
  no rewrite. A low-frequency decide-timer (a few Hz) runs a join check in WANDER
  and a symmetric leave check in GROUPED, routing through the *existing* grouping
  machinery (`_add_to_group` / `_remove_from_group`). Join uses a Granovetter
  per-character threshold `T = 1 + round(independence * MAX_T)`: sociable chars
  join a single neighbor, loners need a near-mob (or never).
- **Hysteresis is mandatory**: dual enter/leave thresholds (leave count strictly
  below join `T`) + a minimum dwell time, or characters on a crowd-size boundary
  visibly vibrate.
- **Chat commands stay authoritative.** `!follow`/`!leave`/`!join` set a manual-hold
  timer on `touch()` that suppresses the autonomous check, so the AI only fills
  the silence and never undoes a viewer's intent.
- `restlessness` also multiplies the existing `JUMP_CHANCE`/`IDLE_CHANCE`/facing
  re-roll cadence — visible variety even before any grouping logic.
- Only count clusters the awareness layer marks reachable (same/adjacent surface),
  or a character walks into a wall under an unreachable slot.

## L5 — Emotion (`character.py`, `settings.py`, renderer)

Add a continuous emotion orthogonal to `Mode` (a character can be panicked while
wandering), driving both the face and movement
(`docs/research/npc-emotion-models.md` 1, 2):

- **Two floats per character**: `valence` [-1,1] and `arousal` [0,1] (drop PAD's
  dominance; drop OCC appraisal — chat commands *are* the appraised events). Plus
  per-agent `susceptibility`/`expressiveness` seeded from the username.
- **Updated every frame, before the mode branch**, by three sources:
  (1) exponential decay toward neutral (`x *= EMOTION_DECAY_PER_SEC ** dt`) — the
  single most important legibility mechanic; (2) **proximity-weighted contagion**
  toward neighbors' emotion, scaled by `susceptibility` and sender `expressiveness`
  (reuses the shared neighbor records, no new scan); (3) a small **crowding bump**
  to arousal from neighbor count.
- **Quantize to the three existing faces** with hysteresis (enter/exit thresholds
  or a hold time so faces don't strobe): `panic` when valence low + arousal high,
  `battle` when arousal high, else `default`. `Character.surface` then selects the
  frame list by `emotion_face()` — which is why the renderer needs all three
  variants (plumbing #2).
- **Modulates movement**: arousal scales speed and restlessness up; low valence
  damps speed (distress slows movement) and widens separation (withdraw). New
  `settings.py` gains: `EMOTION_DECAY_PER_SEC`, `CONTAGION_RATE`,
  `CONTAGION_RADIUS`, `AROUSAL_SPEED_GAIN`, `CROWD_AROUSAL`. Decay must outrun
  contagion at rest or panic becomes permanent.

## Why this order

L1-L2 are the immediate visual wins a viewer notices (movement weight, sprites
that face where they walk). L3 needs the shared neighbor records; L4 and L5 both
build on L3's awareness and the same records, so the plumbing pays for itself
three times. Personality (L4) and emotion (L5) are independent of each other and
can ship in either order once L3 exists. Rationale and alternatives are in
[0004-layered-agent-behavior](../decisions/0004-layered-agent-behavior.md); term
definitions in [agent-behavior-glossary](../domain/agent-behavior-glossary.md).
