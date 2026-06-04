# Crowd Simulation & Crowd-Awareness for Agents

Research brief. RESEARCH ONLY -- no code here; concrete recommendations are
mapped to the files an implementer would touch.

Goal: evolve our current "single horizontal separation push" into genuine
crowd-awareness -- characters that sense the crowd around them (density,
neighbours, heading) and respond in ways that read as lively but not chaotic --
while staying cheap enough for up to `MAX_CHARACTERS = 100` agents in a 2D
pygame side-scroller.

---

## 0. Where we are today (the baseline this builds on)

The sim already has the skeleton of crowd-awareness:

- `World.update` (`twitch_playground/sim/world.py`) gathers
  `positions = [c.pos for c in self.characters.values()]` once per frame and
  passes the full list to every character's `update`. So each agent already
  receives every other agent's position -- this is an O(N) build of an O(N)
  neighbour list, i.e. O(N^2) total reads per frame (see perf section).
- `steering.separation_push` (`twitch_playground/sim/steering.py`) implements
  exactly **one** of Reynolds' three rules -- separation -- and only on the
  horizontal axis. It loops the neighbour list, keeps neighbours within
  `HSEP_Y_BAND` vertically (same surface) and `HSEP_RADIUS` horizontally, and
  returns a signed px/s nudge clamped to `HSEP_PUSH`.
- `settings.py` exposes the three knobs: `HSEP_RADIUS = 30`, `HSEP_Y_BAND = 12`,
  `HSEP_PUSH = 40`.

So we have separation. We are missing **alignment**, **cohesion**, and any
notion of **local density**. The rest of this brief is about adding those three
in a way that fits the side-scroller's surface-bound, mostly-1D motion model.

A side-scroller insight that shapes every recommendation below: our agents are
not free-floating 2D boids. They are pinned to platform surfaces and move almost
entirely on the **horizontal** axis (vertical motion is gravity/jump, owned by
the Character, not by steering). The `HSEP_Y_BAND` test already encodes this:
"neighbours on roughly my surface." That means crowd-awareness here is
effectively a **1D problem per surface** -- which makes both the math and the
spatial acceleration dramatically simpler than textbook 2D/3D boids.

---

## 1. Techniques summary

### 1.1 Boids / flocking (Reynolds, 1986)

Craig Reynolds showed that three purely *local* steering rules -- each agent
looking only at neighbours within a radius -- produce emergent, lifelike flock
motion with no central controller ([Reynolds, "Flocks, Herds, and Schools",
SIGGRAPH 1987](https://www.red3d.com/cwr/boids/);
[Boids -- Wikipedia](https://en.wikipedia.org/wiki/Boids)):

1. **Separation** -- steer to avoid crowding local neighbours (short-range
   repulsion, strength grows as neighbours get closer). *This is what we have.*
2. **Alignment** -- steer toward the *average heading/velocity* of local
   neighbours. Produces coordinated movement: a group drifting the same way
   keeps drifting the same way.
3. **Cohesion** -- steer toward the *average position* (centre of mass) of local
   neighbours. Produces clumping/grouping: stragglers pull back toward the pack.

Each rule yields a desired-velocity contribution; the final steering is a
**weighted sum**. The character of the flock is entirely in the weights and the
radii:

- Separation weighted too high -> agents scatter and never form a group.
- Cohesion/alignment too high -> a rigid blob that snaps together unnaturally.
- Commonly cited starting weights are small and separation-dominant (e.g.
  alignment/cohesion factors around `0.05--0.1`, separation stronger), then
  tuned by eye -- there is no canonical "correct" set; tuning is the work
  ([Boids algorithm walkthrough, earezki.com](https://earezki.com/ai-news/2026-02-25-boids/);
  [Boids with KD-trees, Medium](https://medium.com/@jorgechedo/boids-simulating-flocking-behavior-with-mathematics-and-kd-trees-be61f8f787f4)).

**Perception / neighbourhood.** Reynolds' agents don't see the whole flock --
only neighbours inside a perception volume: a radius, optionally narrowed to a
forward field-of-view (a sphere with a cone removed from the back). A limited FOV
makes motion more realistic (you react to what's ahead, not behind) and is
cheaper. Two neighbourhood definitions exist: "everyone within radius R" (what we
use) and "the K nearest" -- radius is simpler and fine for us.

### 1.2 Social Force Model (Helbing & Molnar, 1995)

Where boids target birds/fish, the Social Force Model (SFM) targets **walking
pedestrians**, which is much closer to our use case (upright characters on
ground). Pedestrians are modelled as particles driven by "social forces" that
represent internal motivations, not physical contact
([Helbing & Molnar, Phys. Rev. E 51, 4282, 1995, arXiv:cond-mat/9805244](https://arxiv.org/abs/cond-mat/9805244)):

- **Driving force** -- pulls the agent toward its desired destination at a
  preferred speed (in our world, the wander `_facing * WALK_SPEED`, or a group
  slot, is the analogue).
- **Repulsive social force** -- a smoothly decaying (typically exponential)
  push away from other pedestrians that grows steeply as they enter your
  **personal space**. This is a softer, distance-continuous version of our
  linear `separation_push`.
- **Attractive forces** -- toward friends/group members or points of interest
  (our follow-group anchor is an explicit version of this).
- **Border/obstacle force** -- repulsion from walls (our `WALL_MARGIN` clamp and
  platform edges already serve this role, albeit as a hard clamp not a force).

The SFM is valuable to us for three ideas: (a) personal space as a
*continuous, distance-decaying* repulsion rather than a hard radius cutoff;
(b) a **density response** -- crowded agents slow down and yield; (c) it
empirically reproduces the emergent behaviours below from local rules alone.

### 1.3 Perception / awareness done efficiently

"Crowd-awareness" concretely means each agent can cheaply answer: *who is near
me, how dense is it here, and which way is the local crowd heading?* Done naively
(every agent scans every other) this is **O(N^2)** per frame. The standard fix is
spatial partitioning so each agent inspects only nearby candidates:

- **Uniform grid / spatial hash** -- bin agents into fixed-size cells sized to
  the interaction radius; a neighbour query then visits only the agent's cell and
  its immediate neighbours (3x3 in 2D). Membership updates are O(1) as agents
  move, and -- unlike trees -- there's no expensive rebuild each frame, which
  matters precisely because boids never stop moving
  ([Efficient Boid Flocking with spatial grids, Arnauld's blog](https://arnauld-alex.com/scaling-boids-for-multiplayer-games-fast-flocking-with-spatial-grids-and-zero-copy-optimization);
  [Uniform spatial subdivision for Boids, IJARND](https://www.ijarnd.com/manuscripts/v3i10/V3I10-1144.pdf)).
- **Compute the neighbour list once per agent per frame and share it** across all
  three rules instead of re-querying per rule. A reported ~60% drop in per-boid
  update time came from exactly this reuse
  ([Arnauld's blog](https://arnauld-alex.com/scaling-boids-for-multiplayer-games-fast-flocking-with-spatial-grids-and-zero-copy-optimization)).
- **Local density** falls out for free: it's just the neighbour count (or
  count / cell-area) from the same query -- no extra pass.

These techniques scale to >1M boids at ~30fps in optimized engines; the win
grows with crowd size because the grid's constant-factor overhead is amortized
([Arnauld's blog](https://arnauld-alex.com/scaling-boids-for-multiplayer-games-fast-flocking-with-spatial-grids-and-zero-copy-optimization)).
At our N=100 the asymptotics barely matter (see perf section) -- but the *neighbour-list-once* discipline is worth adopting regardless because it's the natural shape for adding alignment + cohesion + density without three separate scans.

### 1.4 Emergent behaviours (lively-but-not-chaotic)

The behaviours that make a crowd read as alive, all emergent from local rules:

- **Lane formation** -- in bidirectional flow, opposing streams self-organize
  into lanes to reduce friction; a hallmark SFM result
  ([Helbing & Molnar 1995](https://arxiv.org/abs/cond-mat/9805244)). In our 1D
  side-scroller this shows up as left-movers and right-movers settling into
  stable passing behaviour instead of jittering through each other.
- **Clustering / grouping** -- cohesion pulls nearby agents into loose clumps
  that drift together (boids).
- **Milling** -- with balanced separation+cohesion and no shared goal, a group
  can settle into slow circulating/idling rather than a directed march; reads as
  a crowd "hanging out."
- **Avoidance** -- agents yield and flow around each other and obstacles rather
  than colliding, the core SFM repulsion result.

The recurring lesson across all sources: **liveliness lives in the balance of
weights, not in adding more rules.** Three local rules + tuned weights is the
whole trick. Over-tuning any single weight is what tips a crowd from "alive" to
either "frozen blob" or "jittery chaos."

---

## 2. Concrete recommendations for our project

Guiding principle: our world is surface-bound and ~1D-per-surface, so port the
*ideas* of boids/SFM, not a literal 2D vector implementation. Everything below
keeps steering as **pure functions over vectors** (the existing `steering.py`
contract) and adds **tunable weights in `settings.py`** -- never hardcoded
inline, matching the project's existing `HSEP_*` / `LAYER_*` convention.

### 2.1 Add alignment and cohesion alongside the existing separation

In `steering.py`, complement `separation_push` with two more horizontal,
same-surface contributions, then sum them weighted. Suggested shape (signed px/s,
same units as the current push):

- **`cohesion_pull(pos, neighbors) -> float`**: average x of same-band neighbours
  within a (larger) cohesion radius, return a nudge toward that mean x. Pulls a
  straggler back toward the local pack. Larger radius than separation.
- **`alignment_nudge(pos, neighbor_velocities) -> float`**: average horizontal
  *facing/velocity sign* of same-band neighbours, return a nudge toward that mean
  heading. Makes a knot of characters drift together instead of milling through
  each other. **Note this needs neighbour velocities/facing, not just positions**
  -- see 2.4.

Then in `Character._wander`, replace the single push with a weighted blend:

```
crowd = (W_SEP * separation_push(...)
         + W_COH * cohesion_pull(...)
         + W_ALI * alignment_nudge(...))
self.velocity.x = walk + crowd   # still clamped to a max nudge
```

Keep separation dominant (it's the collision-avoider); cohesion and alignment
are gentle. Start small and tune by eye, exactly as the boids literature
prescribes.

New `settings.py` knobs (mirroring the existing `HSEP_*` block):

```
# Crowd-awareness weights (dimensionless blend factors on the px/s nudges)
CROWD_SEP_WEIGHT = 1.0
CROWD_COH_WEIGHT = 0.15
CROWD_ALI_WEIGHT = 0.10
# Cohesion/alignment look further than separation
CROWD_COH_RADIUS = 80.0     # px; pull toward local centre-of-mass within this
CROWD_ALI_RADIUS = 80.0     # px; match heading of neighbours within this
CROWD_MAX_NUDGE  = 50.0     # px/s; clamp on the summed crowd force
```

(`HSEP_RADIUS`/`HSEP_Y_BAND`/`HSEP_PUSH` stay as the separation tier.)

### 2.2 Add a cheap local-density sense and let it modulate behaviour

Density is the single most "crowd-aware"-feeling signal and it's nearly free:
it's the same-band neighbour count the steering loop already produces. Surface it
as `local_density(pos, neighbors) -> int` (or normalized float) and use it to:

- **Slow down in a crowd** (SFM density response): scale `WALK_SPEED` down as
  local density rises, so a packed platform shuffles instead of marching. A
  natural, organic-looking effect.
- **Suppress hops when boxed in**: gate the per-frame `JUMP_CHANCE` on low
  density so characters don't pogo on top of each other in a tight clump.
- **Bias idle-pausing up in dense spots**: crowded characters "wait" more,
  reinforcing the milling/hanging-out read.

These are 2-3 line changes in `_wander`'s decision block, each reading one
integer. Knobs: `CROWD_DENSITY_RADIUS`, `CROWD_SLOWDOWN_PER_NEIGHBOR` (capped).

### 2.3 Lane formation (almost free given the above)

Once alignment exists, the side-scroller analogue of lane formation emerges from
a small tweak: when an oncoming neighbour (opposite facing, within separation
radius, ahead in the direction of travel) is detected, bias the separation push
consistently to one side (e.g. always yield rightward). Opposing streams then
self-sort into stable passing lanes instead of head-on jitter. This is a handful
of lines in `separation_push` keyed on neighbour facing -- which is another
reason 2.4 (passing velocity/facing, not just position) is the enabling change.

### 2.4 The one real plumbing change: pass velocities/facing, not just positions

Alignment and lane logic need neighbours' **heading**, but `World.update`
currently passes only positions:

```python
positions = [c.pos for c in self.characters.values()]
for char in self.characters.values():
    char.update(dt, positions, self.platforms)
```

Recommendation: pass lightweight neighbour records carrying `(pos, facing)` (or
`(pos, velocity.x)`) instead of bare positions. Cheapest form: build two parallel
lists, or a list of small tuples, once per frame. `Character.update`'s signature
widens from `neighbor_positions` to `neighbors` accordingly. This is the only
structural change; everything else is additive pure-function steering + settings.

### 2.5 Spatial acceleration: recommend deferring it, with a clear trigger

A uniform grid / spatial hash is the textbook fix for O(N^2), **but at N=100 on a
single ground-width screen it is almost certainly premature** (see perf). The
honest recommendation:

- **Now:** keep the single shared neighbour list per agent (already the shape of
  the code). When adding cohesion/alignment/density, compute **one** filtered
  neighbour list per agent per frame and feed all rules from it -- do *not* write
  three separate scans. This captures the biggest practical win (neighbour-list
  reuse) with zero new data structure.
- **Later, only if profiling shows the per-frame neighbour loop dominating** (or
  if `MAX_CHARACTERS` is raised well past 100): add a **1D horizontal bucket
  grid**. Because motion is surface-bound, you don't need a 2D grid -- bucket
  agents by `floor(pos.x / cell)` per surface-band, query own-bucket +/- 1.
  Sized to the largest interaction radius (`CROWD_COH_RADIUS`), this turns the
  neighbour query into a near-constant-time lookup. Build it once in
  `World.update`, hand each agent its candidate slice.

Trigger to revisit: frame budget. At `FPS = 12` we have ~83ms/frame -- enormous
headroom -- so the grid is a "when we raise the cap" item, not a "now" item.

---

## 3. Performance implications at N = 100

- **Current cost.** The neighbour interaction is O(N^2): 100 agents x 100
  positions = 10,000 cheap comparisons per frame, each an abs-diff and a
  branch. At `FPS = 12` (the deliberate stop-motion render rate, see
  `settings.py`) that's ~120k comparisons/sec -- trivial for Python/pygame.
- **Adding cohesion + alignment + density.** These reuse the *same* per-agent
  neighbour scan if implemented as one filtered list feeding all rules (2.1/2.5).
  Cost stays O(N^2) with a slightly larger constant (a few more accumulations per
  neighbour), still ~10k iterations/frame. No asymptotic change.
- **The trap to avoid:** implementing separation, cohesion, alignment, and
  density as four independent loops over the neighbour list quadruples the
  constant for no reason. One scan, multiple accumulators.
- **When a grid actually pays off.** The uniform-grid win grows with N and only
  beats brute force once N is large enough to amortize bucketing overhead
  ([Arnauld's blog](https://arnauld-alex.com/scaling-boids-for-multiplayer-games-fast-flocking-with-spatial-grids-and-zero-copy-optimization)).
  At N=100 with a 12fps budget, brute force is the simpler, faster-to-ship,
  and very likely faster-in-practice choice. Reserve the 1D bucket grid for a
  future `MAX_CHARACTERS` increase or if profiling proves the loop hot.
- **Pythonic note:** if the neighbour loop ever does show up in a profile before
  N grows, the cheap win is vectorizing the position comparisons with numpy
  arrays in `World.update`, not reaching for a grid -- but neither is warranted at
  current scale.

**Bottom line on perf:** at N=100 the algorithm choice is a non-issue; spend the
effort on *tuning the weights* (where all the liveliness lives), not on premature
spatial optimization.

---

## 4. Scope notes / relation to sibling research

This brief is deliberately scoped to **crowd awareness and density sensing**
(boids rules, SFM, neighbour/density queries, emergent crowd motion). Adjacent
concerns are covered by sibling research tickets and intentionally not duplicated
here: general single-agent steering behaviours; crowd-following vs. individual
independence and personality variation; and emotion models / emotional contagion.
Where those land, the per-agent crowd weights proposed in 2.1 are the natural
hook for per-personality variation (e.g. a "loner" gets a higher separation /
lower cohesion weight).

---

## 5. Sources

- [Craig Reynolds, "Flocks, Herds, and Schools: A Distributed Behavioral Model" (SIGGRAPH 1987) + Boids overview](https://www.red3d.com/cwr/boids/)
- [Boids -- Wikipedia](https://en.wikipedia.org/wiki/Boids)
- [Boids algorithm walkthrough (three rules, weights), earezki.com](https://earezki.com/ai-news/2026-02-25-boids/)
- [Boids with mathematics and KD-trees (neighbourhood definitions, weights), Medium](https://medium.com/@jorgechedo/boids-simulating-flocking-behavior-with-mathematics-and-kd-trees-be61f8f787f4)
- [Helbing & Molnar, "Social Force Model for Pedestrian Dynamics", Phys. Rev. E 51, 4282 (1995), arXiv:cond-mat/9805244](https://arxiv.org/abs/cond-mat/9805244)
- [Helbing et al., "Self-Organizing Pedestrian Movement" (2001)](https://journals.sagepub.com/doi/10.1068/b2697)
- [Efficient Boid Flocking with spatial grids and neighbour-list reuse, Arnauld's blog](https://arnauld-alex.com/scaling-boids-for-multiplayer-games-fast-flocking-with-spatial-grids-and-zero-copy-optimization)
- [Uniform spatial subdivision to improve the Boids algorithm, IJARND](https://www.ijarnd.com/manuscripts/v3i10/V3I10-1144.pdf)
