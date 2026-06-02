# Research: Natural NPC Movement & Steering Behaviors

Research brief for making our sidescroller characters move and idle in a way that
reads as *alive* rather than robotic. Grounded in the current code
(`twitch_playground/sim/steering.py`, `sim/character.py`, `settings.py`) and the
shared contract (`docs/design/sidescroller-contract.md`). RESEARCH ONLY — no code
changed here; this is a spec for an implementer.

## TL;DR — cheapest high-impact wins, in order

1. **Flip the sprite by facing.** We already track `_facing`, but the renderer
   never flips, so everyone always faces the same way. One-line fix in the
   renderer (`pygame.transform.flip`). Biggest visual payoff per byte of code.
2. **Replace random direction flips with a real wander steering force.** Today a
   character picks `random.choice((-1, 1))` after each pause and otherwise walks
   in a straight line until it hits a wall. A persistent, slowly-drifting heading
   (Reynolds wander) makes meandering look intentional, not coin-flip jerky.
3. **Ease velocity instead of bang-banging it.** `velocity.x` snaps between `0`
   and `WALK_SPEED` instantly. Accelerate toward a desired velocity with a capped
   steering force so starts/stops read as weight, not teleports.
4. **Add arrival slowdown** for GROUPED followers (they currently run at full
   `WALK_SPEED` then hard-snap to the slot) and richer **idle micro-behaviors**
   (look-arounds, weight shifts) so a paused character isn't a frozen prop.

Wins 1 and 2 are the ones a viewer will notice immediately. Win 3 is what
separates "moves correctly" from "feels good."

---

## 1. Techniques (the theory)

### Steering = desired − velocity

Craig Reynolds' framing (the foundational
[*Steering Behaviors For Autonomous Characters*](https://www.red3d.com/cwr/steer/),
1999) treats a character as a point mass with a velocity. Every behavior produces
a **desired velocity**; the **steering force** is the difference between what the
character wants and what it's currently doing:

```
steering = desired_velocity - current_velocity
steering = clamp(steering, max_force)     # how fast it CAN change direction
velocity = clamp(velocity + steering * dt, max_speed)   # how fast it CAN go
position += velocity * dt
```

Two separate caps do different jobs (well explained in
[*The Nature of Code*, ch. 5](https://natureofcode.com/autonomous-agents/)):

- **`max_speed`** caps the velocity magnitude — top walking speed.
- **`max_force`** caps the steering force — how *sharply* it can turn or how
  quickly it can change speed. A small `max_force` gives a heavy, lumbering feel
  (ramps up slowly); a large one is twitchy and responsive.

This single equation is what makes starts and stops read as acceleration with
weight rather than instantaneous velocity changes.

### Seek and Arrive

- **Seek**: desired velocity points at the target, scaled to `max_speed`. Reaches
  the target at full speed (overshoots and orbits).
- **Arrive**: same, but inside a *slowing radius* the desired speed is scaled down
  linearly with distance so the character decelerates to a graceful stop. From
  *The Nature of Code*:

  ```js
  if (d < slowRadius) desired.setMag(map(d, 0, slowRadius, 0, maxspeed));
  else                desired.setMag(maxspeed);
  ```

  This is exactly the behavior our GROUPED followers want (walk to the slot, ease
  in) instead of full-speed-then-snap.

### Wander — the canonical "projected circle" algorithm

The key insight (Reynolds, elaborated in *The Nature of Code*): naive wandering
picks a brand-new random direction each frame, which produces jittery, robotic
twitching. The fix is to make the randomness *coherent over time* by constraining
it to a small angular drift:

1. Project a point ahead of the character along its current velocity
   (`wander_distance`, ~25 px in the reference).
2. Put a **wander circle** of radius `r` (~20 px) at that projected point.
3. Keep a persistent angle `wander_theta` (a class field, not a local).
4. **Each frame**, nudge `wander_theta` by a *small* random delta within a
   `displace_range` (e.g. ±0.3 rad) — drift it, don't reroll it.
5. The target is the point on the circle at `wander_theta`; steer (seek) toward
   it.

Because `wander_theta` persists and only drifts a little per frame, the heading
changes smoothly — long-term meandering, short-term stability. That coherence is
the whole point.

For our **horizontal-only** world this collapses to a 1-D version: maintain a
persistent desired horizontal heading/speed and let it drift slightly each frame
(plus occasional larger reorientations), rather than `random.choice((-1, 1))`.

### Velocity-based facing (and the 2D sprite flip)

In Reynolds' model, characters face their direction of travel automatically. For a
2D sidescroller this reduces to: **flip the sprite horizontally by the sign of
`velocity.x`** (or of the persistent facing). Standard implementations
([2D Platformer flip guide](https://medium.com/@eveciana21/2d-platformer-how-to-flip-your-sprite-in-game-eecc2ad0f631),
[GameDevMix: player flip methods](https://www.gamedevmix.com/blog/player-flip-methods/)):

- Engine sprite-flip flag (`flipX`) or a negative X scale; in pygame the
  equivalent is `pygame.transform.flip(surface, True, False)`.
- **Only flip when the direction actually changes**, not every frame (cheaper, and
  avoids visual flicker).
- Guard the flip with a small **deadzone / hysteresis** so a sprite near zero
  velocity (e.g. our `separation_push` nudging a near-idle character) doesn't
  rapidly flicker left/right. Reuse something like `WALK_THRESHOLD` as the cutoff.

### Idle / wander micro-behaviors

A character that holds a single pose (or one looping clip) reads as a frozen prop;
subtle motion signals "alive" for very little animation cost
([MoCap Online crowd/NPC guide](https://mocaponline.com/blogs/mocap-news/crowd-npc-animation-guide),
[TV Tropes: Idle Animation](https://tvtropes.org/pmwiki/pmwiki.php/Main/IdleAnimation)).
Cheap, high-value micro-behaviors:

- Head turns / look-arounds, weight shifts, a small breathing bob.
- **Randomize and stagger** idle behaviors across characters so a crowd doesn't
  pulse in lockstep — non-repetitive scheduling is what kills the "robot army"
  look.
- Schedule them the way we already schedule pauses/jumps: a per-second Poisson
  chance multiplied by `dt` (frame-rate-independent), picking from a small menu of
  micro-actions.

### Low-FPS / stop-motion constraints

Our render is ~12 fps and animation playback is `ANIM_FPS = 8`. Relevant findings
([*Frame Rate in Animation — Why Less is More*](https://nicholasjean.medium.com/frame-rate-in-animation-why-less-is-more-1fe11b328193),
[Bricks in Motion: on ones and twos](https://www.bricksinmotion.com/forums/topic/17194/24-fps-on-ones-and-twos/)):

- 12 fps **is** the classic "on twos" stop-motion rate (Aardman, etc.) — our low
  rate is a legitimate stylistic choice, not a defect. Lean into snappy, stylized
  motion rather than fighting for smoothness.
- **Crucial**: keep *position integration* continuous (delta-time based) even
  though *animation frames* are few. The eye reads motion primarily from
  displacement over time, so sub-pixel easing of `velocity`/`pos` still reads as
  smooth acceleration at 12 fps — the choppiness is only in the sprite's drawn
  pose, not its travel. This means **acceleration easing (win #3) is worth doing
  even at 12 fps.** We already integrate with `dt`, so we're set up for this.
- What does *not* read well at low fps: anything that relies on many in-between
  poses (fast spins, smooth turn arcs). Favor discrete state changes (face left /
  face right, walk / idle / jump) with eased *position*, not eased *rotation*.
- Direction flips and behavior decisions should remain `dt`-scaled (as
  `JUMP_CHANCE`/`IDLE_CHANCE` already are) so behavior is identical regardless of
  the actual render rate.

---

## 2. Recommendations mapped to our code

### A. Sprite flip by facing — renderer (cheapest win)

**Problem.** `character.py` maintains `self._facing` (`-1`/`1`) and updates it at
platform edges and after pauses, but `Character.surface` returns the frame
unmodified and the scene renderer draws it as-is. Every character faces the sheet
default direction regardless of travel.

**Fix.**
- Expose facing as public read-only state for the renderer — e.g. rename/alias
  `_facing` to `facing` (the contract already publishes `velocity`, so deriving
  facing from `sign(velocity.x)` with a `WALK_THRESHOLD` deadzone is also valid
  and needs no new field).
- In the scene renderer (owned by the World track — `render/scene.py`, *not*
  editable from the Sim track), flip when facing left:
  `frame = pygame.transform.flip(char.surface, True, False)` when `facing < 0`.
- Add hysteresis so a near-zero `velocity.x` (e.g. only `separation_push` active)
  doesn't flicker the flip. Only change the stored facing when speed exceeds
  `WALK_THRESHOLD`.

**Ownership note.** The Sim track owns `character.py`/`settings.py`; the actual
flip blit lives in `render/scene.py` (World track). This is a small coordination
point: Sim exposes `facing`, World consumes it. Decide direction of the default
sheet pose (which sign means "unflipped") and record it in the contract.

### B. Real wander force — `steering.py` + `character.py`

**Problem.** `_wander` walks in a straight line at `self._facing * WALK_SPEED`
until it hits a wall/edge, then reverses; new directions only come from
`random.choice((-1, 1))` after an idle pause. Reads as ping-pong, not strolling.

**Fix (1-D wander, horizontal).** Add a pure helper to `steering.py` mirroring
the existing pure-function style (it already houses `separation_push`):

- Maintain a persistent `self._wander_heading` (a signed desired speed, or an
  angle) on the Character.
- Each frame, drift it by a small random delta (`±WANDER_DISPLACE` per second,
  `dt`-scaled), and occasionally apply a larger reorientation. Clamp to
  `±WALK_SPEED`.
- The desired horizontal velocity becomes `wander_heading` (plus
  `separation_push`), and we *steer* toward it (see C) rather than assigning it
  directly.
- This subsumes the current behavior: edge/wall turnarounds in
  `_apply_horizontal_bounds` should flip the *heading*, and idle-pause exits
  should nudge it, not hard-reroll `_facing`.

New settings: `WANDER_DISPLACE` (rad/s or px/s of heading drift),
`WANDER_REORIENT_CHANCE` (per-second chance of a bigger turn).

### C. Acceleration easing / max-force — `character.py` + `settings.py`

**Problem.** `self.velocity.x = walk + separation_push(...)` sets velocity
instantly. A character goes 0 -> 60 px/s in one frame (teleport feel), and
stops just as abruptly.

**Fix.** Integrate toward a desired velocity with a capped force:

```
desired_vx = wander_heading + separation_push(...)
steer_x = clamp(desired_vx - velocity.x, -MAX_FORCE * dt_or_accel, +...)
velocity.x = clamp(velocity.x + steer_x, -MAX_SPEED, MAX_SPEED)
```

- `settings.MAX_SPEED = 70.0` **already exists but appears unused** by
  `character.py` (which only references `WALK_SPEED`). This is the natural cap to
  start applying. Worth confirming and wiring up, or removing if truly dead.
- Add `WALK_ACCEL` (px/s^2) / `MAX_FORCE` to control ramp feel. Tune so a
  character reaches `WALK_SPEED` in ~0.2–0.4 s (a few frames at 12 fps) — fast
  enough to feel responsive, slow enough to show weight.
- Note: `_update_emoting` already does `self.velocity.x *= 0.6` — a frame-rate
  *dependent* exponential decay (it eases differently at 12 fps vs 60). When
  generalizing easing, make the decay `dt`-based for consistency.

### D. Arrival slowdown for GROUPED — `character.py`

**Problem.** `_move_toward_slot` runs at full `WALK_SPEED` until within
`GROUP_ARRIVE_RADIUS` (4 px), then snaps `pos = group_slot` and zeroes velocity.
A hard stop after full-speed travel.

**Fix.** Apply Reynolds *arrive*: inside a slowing radius (say
`GROUP_SLOW_RADIUS`, larger than the 4 px arrive radius), scale desired speed
linearly from `WALK_SPEED` down to 0 with distance. Keep the existing
arrive-radius snap as the final settle. Combined with easing (C) this gives a
natural decelerate-and-settle. (Heads-up: the
[grouped-walk-to-slot timing gotcha](../../.charm/kb/gotchas/grouped-walk-to-slot-time-is-unbounded.md)
already notes arrival time scales with spawn separation; arrival easing slightly
lengthens the tail end, so tests that loop-until-arrived should keep generous
frame budgets.)

### E. Idle micro-behaviors — `character.py` + `assets/provider.py`

**Problem.** During an idle pause the character just plays the `idle` clip;
nothing distinguishes one paused character from another, and pauses are the only
idle variety.

**Fix (incremental).**
- Cheapest: stagger existing idle so a crowd doesn't pulse together — already
  partly true via per-character random pause timing; extend by randomizing
  `frame_index` start offset so idle loops are out of phase.
- Next: add a small menu of micro-actions schedulable from the same
  `chance * dt` mechanism that drives `JUMP_CHANCE`/`IDLE_CHANCE` — e.g. a brief
  "look around" (flip facing without moving) or a one-shot fidget clip. This needs
  a new short clip in `SpriteSet` (`assets/provider.py`), so it's a bigger lift;
  schedule it like the existing one-shot `hug` emote.

---

## 3. Mapping summary

| Technique | Our file(s) | Concrete change | Effort | Impact |
|---|---|---|---|---|
| Velocity-based sprite flip | `render/scene.py` (consume), `character.py` (expose `facing`) | `pygame.transform.flip` on facing<0, with deadzone | tiny | high |
| Coherent wander force | `steering.py`, `character.py`, `settings.py` | persistent drifting heading; replace `random.choice` flips | medium | high |
| Acceleration easing (max-force/max-speed) | `character.py`, `settings.py` | steer toward desired vx; wire up unused `MAX_SPEED`; add `WALK_ACCEL` | medium | high |
| Arrive slowdown (GROUPED) | `character.py`, `settings.py` | linear speed scale inside a slow radius before the snap | small | medium |
| Idle micro-behaviors | `character.py`, `assets/provider.py` | phase-offset idles now; scheduled fidget/look-around clip later | small→medium | medium |
| Frame-rate-independent decay | `character.py` | make `velocity.x *= 0.6` emote decay `dt`-based | tiny | low (correctness) |

---

## 4. Sources

- Craig W. Reynolds, *Steering Behaviors For Autonomous Characters* (1999) — the
  foundational paper (seek, flee, arrive, pursue/evade, wander):
  https://www.red3d.com/cwr/steer/
- Daniel Shiffman, *The Nature of Code*, ch. 5 "Autonomous Agents" — working code
  for the steering equation, max-force vs max-speed, arrive, and the canonical
  projected-circle wander: https://natureofcode.com/autonomous-agents/
- Eric Veciana, *2D Platformer: How to Flip your Sprite in Game* — flipX vs scale,
  flip-on-change: https://medium.com/@eveciana21/2d-platformer-how-to-flip-your-sprite-in-game-eecc2ad0f631
- GameDevMix, *3 methods for flipping your player character*:
  https://www.gamedevmix.com/blog/player-flip-methods/
- MoCap Online, *Crowd & NPC Animation Guide* — idle/micro-behavior value and
  non-repetitive scheduling: https://mocaponline.com/blogs/mocap-news/crowd-npc-animation-guide
- TV Tropes, *Idle Animation* — why a still character reads as broken:
  https://tvtropes.org/pmwiki/pmwiki.php/Main/IdleAnimation
- Nicholas Jean, *Frame Rate in Animation — Why Less is More* — low-fps/on-twos
  stylistic rationale: https://nicholasjean.medium.com/frame-rate-in-animation-why-less-is-more-1fe11b328193
- Bricks in Motion forum, *24 fps on ones and twos* — on-twos = effective 12 fps
  stop-motion: https://www.bricksinmotion.com/forums/topic/17194/24-fps-on-ones-and-twos/
