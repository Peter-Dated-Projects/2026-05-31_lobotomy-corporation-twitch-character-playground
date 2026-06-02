# T-024: Emotion models & emotional contagion for NPCs

Research brief for the Lobotomy Corporation Twitch character playground.
Goal: drive each on-screen character's face (our existing `default` / `battle` /
`panic` states) and movement from a cheap, legible emotion model, and let one
character's mood spread to its neighbors so the crowd "feels" like a single
organism reacting to chat.

The bar: a Twitch-stream crowd of a few dozen chibi characters running at 60 fps
in pygame. We want something believable and tunable, **not** an academic
affective-computing engine. Everything below is filtered through that lens.

---

## 1. Techniques summary

### 1.1 Two families of emotion model: appraisal vs dimensional

**OCC (Ortony, Clore & Collins) — appraisal model.** Events are *appraised*
against an agent's goals/standards to produce one of **22 discrete emotion types**
(joy, fear, anger, pride, gloating, ...). It is the de-facto standard for
"cognitive" game NPCs because it explains *why* an emotion arises: an event is
desirable or undesirable relative to a goal. The cost is that you need goals,
events, and appraisal rules — heavyweight for ambient crowd characters.

**PAD (Pleasure-Arousal-Dominance, Mehrabian) — dimensional model.** Every
emotional state is a point in a continuous **3D space**: Pleasure (valence,
pleasant<->unpleasant), Arousal (calm<->excited), Dominance (submissive<->in-control).
PAD is *not* an appraisal theory — it is a compact representation. Its appeal for
games: it is just three floats you can blend, interpolate, decay, and average
across neighbors with ordinary vector math. A discrete emotion is recovered by
finding the nearest labelled region in PAD space.

**They compose, they don't compete.** The well-known game engines layer them:
**GAMYGDALA** and **ALMA** appraise events with OCC, then project the result into
PAD space when the engine wants a single blendable mood vector. ALMA explicitly
separates three time-scales: short-lived **emotion** (seconds), slower **mood**
(minutes, a decaying running average of recent emotion), and fixed **personality**
(per-agent traits that bias both).

### 1.2 Mood vs transient emotion, and decay

The recurring pattern across ALMA / GAMYGDALA / virtual-agent work:

- **Emotion** is a fast, spiky impulse from a single event ("got hugged", "an
  ordeal spawned").
- **Mood** is a slow-moving baseline — a leaky integral of recent emotion that the
  agent returns toward when nothing is happening.
- Both **decay exponentially** toward a neutral resting point: `x <- x * exp(-k*dt)`,
  or the cheaper per-frame equivalent `x <- x * pow(decay_per_sec, dt)`. Emotion
  uses a large `k` (decays in seconds); mood uses a small `k` (decays over
  minutes). This is the single most important mechanic for legibility — without
  decay, states latch and the crowd looks frozen.

### 1.3 Emotion as a state machine in games

For animation/behavior, shipped games rarely expose the full 22-emotion or
continuous-PAD surface. They quantize to **a small set of discrete states** and run
a finite state machine: events (or crossing a threshold in the underlying
continuous value) trigger transitions, and each state drives **both** animation and
behavior parameters. Industry animation guidance is blunt about it: **body language
and movement carry more emotional signal than the face** — a frightened character
reads as frightened from posture, speed, and "glancing back", more than from its
eyes. Documented fear response decomposes into **freeze / flight / fight**, each
with a distinct movement signature.

Empirically, **negative/low-valence states slow voluntary movement**, while **high
arousal raises movement speed and jitter**. So the two PAD axes we care about map
cleanly onto our knobs: arousal -> speed & restlessness, valence -> willingness to
approach others vs withdraw.

### 1.4 Emotional contagion (the crowd-consciousness mechanic)

This is the headline feature: one agent's emotion propagates to nearby agents, so a
single "panic" trigger ripples outward instead of staying local. Two research
lineages, surveyed together in Adamatti/van der Wal et al.'s systematic review of
emotion contagion in agent-based crowds:

**Thermodynamic / ASCRIBE (Bosse et al.).** Treats emotion like heat flowing
between bodies. Each agent has an intensity that is continuously pulled toward a
weighted average of its neighbors' intensities. The transfer on each channel
depends on the **sender's expressiveness**, the **receiver's openness/susceptibility**,
and the **channel strength** (how connected the two are — usually a function of
distance/proximity). It is a system of differential equations; integrated per
frame it is just "nudge my emotion toward my neighbors' emotion, scaled by how
close and how susceptible I am."

**Epidemiological / Durupinar (dose-threshold, SIS-style).** Emotion spreads like
infection: an agent accumulates a "dose" from emotional neighbors and *flips* state
once it crosses a threshold, then recovers over time. Durupinar maps the **OCEAN
personality traits** to contagion parameters so you get crowd archetypes from
"audience" (low spread) to "mob" (high spread) by tuning susceptibility/expressiveness.

**Concrete update structure** (from the ACSEE crowd model, ar5iv:1902.00380, a
representative ASCRIBE-derived formulation):

```
# external (caught) emotion increment from neighbor j
delta_ext(i<-j) = sigmoid_falloff(distance_ij) * e_i * A(j->i) * B(i->j)
#   A = how strongly j sends (expressiveness)
#   B = how open i is to receiving (susceptibility)
#   sigmoid_falloff -> ~1 when close, ->0 when far
e_i(t) = e_i(t-1) + sum_j delta_ext(i<-j) + internal_event_delta - decay
```

Validated finding worth stealing: with contagion **on**, simulated crowds match
real crowd trajectories better than without, and crucially they reproduce the
**initial lag** — it *takes time* for fear to spread through a crowd. That lag is a
feature, not a bug: it is what makes a ripple look like a ripple.

### 1.5 Keeping it cheap at our scale

Full ASCRIBE/Durupinar assume goals, OCEAN vectors, and N-body neighbor coupling.
For a few dozen chibis we can collapse all of it to:

- **One scalar or a 2D (valence, arousal) vector per character** instead of 22 OCC
  emotions or full 3D PAD (dominance buys us little for ambient crowd characters).
- **Reuse the neighbor list we already compute** for separation steering
  (`steering.separation_push` already takes `neighbor_positions`) — contagion adds
  no new spatial query, just an averaging pass over the same neighbors.
- **Quantize to our three existing face states** for rendering, while keeping the
  continuous value internally so transitions are smooth and hysteretic.

---

## 2. Recommendations for this project

### 2.1 Minimal per-character emotion state

Add a tiny, continuous emotion to `Character`, distinct from `Mode` (which is
*behavioral*: WANDER/GROUPED/EMOTING). Emotion is orthogonal — a character can be
panicked *while* wandering or grouped.

```python
# in Character.__init__
self.arousal = 0.0    # 0 = calm, 1 = maxed out
self.valence = 0.0    # -1 = distressed, 0 = neutral, +1 = happy
# per-character personality bias (set once at spawn, e.g. from username hash)
self.susceptibility = random.uniform(0.5, 1.0)   # how much neighbors move me
self.expressiveness = random.uniform(0.5, 1.0)   # how much I move neighbors
```

Two floats (valence, arousal) is the sweet spot: enough to separate "excited &
happy" from "excited & terrified", cheap to decay and average, and trivially
quantized to a face. `susceptibility`/`expressiveness` are the Durupinar-style
per-agent knobs that make the crowd feel heterogeneous (some characters are calm
anchors, some are panic amplifiers) — derive them deterministically from the
username so a given viewer always behaves consistently.

**Quantize to our existing faces** (the renderer's `compose_character(emotion=...)`
already accepts `"default"`/`"battle"`/`"panic"` and falls back to `"default"` for
unknown keys — see `_face()` in `lobcorp_renderer.py`):

```python
def emotion_face(self) -> str:
    if self.valence < -0.35 and self.arousal > 0.4:
        return "panic"          # distressed + agitated
    if self.arousal > 0.5:
        return "battle"         # fired up (positive or aggressive high-arousal)
    return "default"            # calm / neutral baseline
```

Use **hysteresis** (different enter vs exit thresholds, or require the value to
hold for ~0.2 s) so faces don't strobe when a value sits on a boundary.

### 2.2 What drives transitions (the three event sources)

1. **Chat commands.** A command is an OCC-style appraised event: apply an
   instantaneous impulse to the target's valence/arousal. e.g.
   `!panic -> arousal += 0.8, valence -= 0.7`; `!cheer -> arousal += 0.5, valence += 0.6`;
   the existing `!hug` keeps its EMOTING clip *and* nudges `valence += 0.4` on both
   participants. Clamp to [-1, 1] / [0, 1] after each impulse.
2. **Proximity / crowding.** Reuse the neighbor count already available in
   `_wander`. Dense packing raises arousal slightly (crowd tension); isolation lets
   it decay. This is free — it piggybacks on the separation neighbor list.
3. **Contagion from neighbors.** Each frame, pull this character's emotion toward
   the proximity-weighted average of its neighbors', scaled by susceptibility (see
   2.4). This is what turns one `!panic` into a crowd wave.

Everything decays toward neutral every frame (2.4), so absent any event the crowd
relaxes back to `default` faces.

### 2.3 How emotion modulates movement

Modulate the existing movement constants by the emotion scalars rather than adding
new movement code. In `_wander`:

- **Speed** scales with arousal: `walk_speed = settings.WALK_SPEED * (1 + AROUSAL_SPEED_GAIN * arousal)`.
  Low valence damps it back down (distress slows voluntary movement), matching the
  empirical finding — net effect: panicked = fast & erratic, sad = sluggish.
- **Restlessness** scales with arousal: multiply `JUMP_CHANCE` up and `IDLE_CHANCE`
  down with arousal, so agitated characters hop and pace instead of taking idle
  pauses.
- **Sociability** scales with valence: feed valence into grouping willingness —
  happy characters tolerate tighter clusters (smaller separation push), distressed
  ones want more space (stronger separation, the "flight/withdraw" read). This hooks
  into `steering.separation_push` by scaling its output.
- **(Optional) flight from a panic source.** A high-arousal/low-valence character
  can bias `_facing` away from the nearest panic neighbor — the cheapest possible
  nod to fear's flight response, no new pathfinding.

Keep all gains as named constants in `settings.py` (e.g. `AROUSAL_SPEED_GAIN`,
`EMOTION_DECAY_PER_SEC`, `CONTAGION_RATE`, `CONTAGION_RADIUS`) — consistent with the
repo convention of not hardcoding tunables inline (cf. `LAYER_SCALES`/`LAYER_OFFSETS`).

### 2.4 Integration points (concrete)

**`character.py` — `update()`.** Emotion is behavior-mode-agnostic, so update it on
*every* frame, before the mode branch, so it ticks even while GROUPED or EMOTING:

```python
def update(self, dt, neighbor_positions, platforms, neighbors=None):
    self._update_emotion(dt, neighbors or [])   # NEW: decay + contagion + crowding
    # ... existing mode dispatch unchanged ...

def _update_emotion(self, dt, neighbors):
    # 1. exponential decay toward neutral (the legibility mechanic)
    self.arousal *= settings.EMOTION_DECAY_PER_SEC ** dt
    self.valence *= settings.EMOTION_DECAY_PER_SEC ** dt
    # 2. contagion: nudge toward proximity-weighted neighbor average
    tot_w = 0.0; ar = 0.0; va = 0.0
    for n in neighbors:
        d = self.pos.distance_to(n.pos)
        if d > settings.CONTAGION_RADIUS:
            continue
        w = (1.0 - d / settings.CONTAGION_RADIUS) * n.expressiveness
        ar += w * n.arousal; va += w * n.valence; tot_w += w
    if tot_w > 0:
        rate = settings.CONTAGION_RATE * self.susceptibility * dt
        self.arousal += rate * (ar / tot_w - self.arousal)
        self.valence += rate * (va / tot_w - self.valence)
    # 3. crowding bumps arousal; clamp everything
    self.arousal = min(1.0, self.arousal + settings.CROWD_AROUSAL * len(neighbors) * dt)
    self.arousal = max(0.0, min(1.0, self.arousal))
    self.valence = max(-1.0, min(1.0, self.valence))
```

Note this needs **neighbor `Character` objects** (to read their emotion +
expressiveness), whereas `update()` today only receives `neighbor_positions`. The
World update loop will need to pass the neighbor objects (or a small
`(pos, arousal, valence, expressiveness)` snapshot list) in addition to / instead
of bare positions. Computing the neighbor list once in World and sharing it with
both separation and contagion keeps it O(N * neighbors), not O(N^2) over the whole
crowd.

**Renderer — the emotion arg.** `compose_character(emotion=...)` already does the
right thing, but **runtime emotion is not currently wired through**: the
`SpriteSet` clips are pre-rendered at the resting `"default"` emotion only (see the
note at `lobcorp_renderer.py` ~line 226 and the `walk` clip's `emotion=default` in
the layer-stack KB). To actually show `battle`/`panic` faces we have two options:

- **(Recommended) Pre-render all three emotion variants per clip** at load time and
  have `Character.surface` pick the frame list by `self.emotion_face()`. This keeps
  the hot path a pure dict lookup + blit (no per-frame compositing), which matters
  for the low-CPU goal from the rendering research. Cost is ~3x sprite memory per
  character — fine at a few dozen characters; revisit if the crowd grows large.
- (Alternative) Composite on demand when emotion changes and cache the result.
  Cheaper memory, but adds a compositing spike on every face transition.

`Character.surface` then becomes:

```python
@property
def surface(self):
    frames = self.sprites.clip(self.clip, emotion=self.emotion_face())
    return frames[int(self.frame_index) % len(frames)]
```

with `SpriteSet.clip` (and the provider that builds it) extended to key clips by
emotion. This is the one cross-file change emotion forces: the provider/`SpriteSet`
must hold three face variants, not one.

### 2.5 Suggested defaults to start tuning from

| Constant | Start value | Meaning |
|---|---|---|
| `EMOTION_DECAY_PER_SEC` | `0.4` | emotion retains 40% of its value per second (fast, spiky) |
| `CONTAGION_RATE` | `0.6` | how fast I move toward neighbors' mood |
| `CONTAGION_RADIUS` | `2.5 * SPRITE_W` | only fairly close neighbors infect me |
| `AROUSAL_SPEED_GAIN` | `0.8` | panicked characters move up to ~1.8x `WALK_SPEED` |
| `CROWD_AROUSAL` | `0.05` | mild tension per neighbor per second |

These are deliberately conservative — the contagion lag and decay are what sell the
effect, and both are easy to over-tune into either "nothing spreads" or "everyone
instantly panics forever." Expect to tune `CONTAGION_RATE` and
`EMOTION_DECAY_PER_SEC` together: decay must outrun contagion at the crowd's resting
state or panic becomes permanent.

### 2.6 Scope notes / what to defer

- **Dominance axis**: skip it. Valence+arousal cover faces and movement; dominance
  earns its keep only for social-hierarchy NPCs we don't have.
- **Full OCC appraisal**: skip it. Chat commands *are* our appraised events — we
  don't need goals/standards machinery to assign an impulse to a command.
- **Mood (slow integral)**: nice-to-have, not v0. A single emotion layer with decay
  is enough to demo. Add a slow-decaying `mood` baseline later if characters feel
  too memoryless.

---

## 3. Sources

- [Emotion contagion in agent-based simulations of crowds: a systematic review (Autonomous Agents and Multi-Agent Systems, 2022)](https://link.springer.com/article/10.1007/s10458-022-09589-z) — surveys ASCRIBE (thermodynamic) vs Durupinar (epidemiological) contagion, parameters, and validation.
- [ACSEE: Antagonistic Crowd Simulation Model with Emotional Contagion (arXiv:1902.00380)](https://arxiv.org/pdf/1902.00380) ([readable HTML](https://ar5iv.labs.arxiv.org/html/1902.00380)) — concrete ASCRIBE-derived contagion update equations (distance falloff, send/receive intensities, external+mental emotion split).
- [GAMYGDALA: An Emotion Engine for Games (Popescu, Broekens & van Someren, 2013)](https://ii.tudelft.nl/~joostb/files/Popescu_Broekens_Someren_2013.pdf) — OCC appraisal producing NPC emotions, with on-demand projection to PAD space.
- [Bosse et al. ASCRIBE / contagion validation — Empirical evaluation of computational fear contagion models in crowd dispersions (AAMAS journal)](https://link.springer.com/article/10.1007/s10458-013-9220-6) — shows contagion-on matches real crowd trajectories and reproduces the spread lag.
- [Emotion and Attitude Modeling for Non-player Characters](https://www.researchgate.net/publication/309691036_Emotion_and_Attitude_Modeling_for_Non-player_Characters) — OCC vs PAD for NPCs; combined use.
- [Georgios Yannakakis & Ana Paiva, "Emotion in Games" (Handbook of Affective Computing chapter)](https://people.ict.usc.edu/~gratch/CSCI534/Readings/ACII-Handbook-Games.pdf) — overview of emotion models applied to games, incl. ALMA's emotion/mood/personality layering.
- [Emotion in Game Animation guide (MoCap Online)](https://mocaponline.com/blogs/mocap-news/emotion-animation-games-guide) — body language > face for emotional read; fear = freeze/flight/fight movement signatures; arousal drives speed.
- [Negative emotional state slows down movement speed: behavioral and neural evidence (PMC6754972)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6754972/) — empirical link from low valence to slower voluntary movement.
- [Simulating Panic Amplification in Crowds via Density-Emotion Interactions (AAMAS 2023)](https://www.southampton.ac.uk/~eg/AAMAS2023/pdfs/p1895.pdf) — crowd density amplifies panic (basis for the proximity->arousal rule).
</content>
</invoke>
