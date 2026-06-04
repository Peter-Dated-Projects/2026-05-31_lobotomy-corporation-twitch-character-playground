# Crowd-following vs. independence, and per-character personality variation

Research brief for the Twitch character playground. Goal: make some characters
gravitate to crowds and others stay solitary, in a way that feels alive but is
deterministic and repeatable per viewer. RESEARCH ONLY -- no code changed here.

Scope note: this brief covers the *decision* to follow/break from a crowd and
the *trait model* that biases it. The low-level "how do I steer toward a target
without overlapping" question (separation, arrival, flocking forces) is covered
by the steering-behaviors research; the "what does the crowd around me look
like" sensing question is covered by the crowd-awareness research. This brief
assumes those exist and focuses on the personality layer that sits on top.

---

## 1. Techniques summary

### 1.1 Threshold / contagion models -- when an agent joins or breaks

The canonical model for "do I join the crowd" is **Granovetter's threshold model
of collective behavior**. Each individual has a personal *threshold*: the
fraction (or count) of others already doing something that must be exceeded
before they join in. Low-threshold individuals act first and trigger a chain
reaction; high-threshold individuals only join once a crowd is already large.
The key, counter-intuitive insight is that collective behavior is *not* the
aggregate of individual preferences -- the same population can either fully
converge or barely move depending on the *distribution* of thresholds, not the
average. A crowd with a few zero/low-threshold "instigators" and a spread of
higher thresholds tips; a crowd of uniformly medium thresholds stalls. (See
sources [1], [2], [3].)

This maps almost perfectly onto what we want: give each character a personal
join-threshold. Sociable characters have low thresholds (they join a cluster of
2-3); solitary characters have very high thresholds (they need a near-mob, or
never join autonomously at all). The *variation* across thresholds is what makes
the crowd feel alive -- early joiners seed clusters, loners hold out.

A symmetric idea governs *leaving*: model a leave-threshold or a patience timer,
so an agent peels off when the crowd shrinks below some personal floor or after
it has been grouped "long enough." Herding/information-cascade framing ([2])
also gives a clean mental model: an agent's tendency to follow can be partly
*social* (others are doing it) rather than purely intrinsic.

### 1.2 Personality / trait systems -- where the variation comes from

The standard psychological model is **OCEAN / Big Five**: Openness,
Conscientiousness, Extraversion, Agreeableness, Neuroticism, each a continuous
axis rather than a category ([4], [5], [6]). Game and agent systems use it (or
subsets of it) to drive clustering and adaptive behavior. Two findings matter
for us:

- Personality is best modeled as **continuous scalar axes**, not discrete
  types. That gives smooth variation across a population and lets a trait feed
  directly into a numeric decision.
- Personality is **not expressed uniformly across situations** ([4]) -- the same
  trait should bias different behaviors by different amounts depending on
  context (how big is the nearby crowd, am I already in one, etc.).

For our purposes the full Big Five is overkill. The relevant subset reduces to a
few axes that directly touch the wander/follow/leave decision:

- **Sociability / gregariousness** (a slice of Extraversion + Agreeableness):
  how strongly this character is drawn to other characters. This is the primary
  axis -- it sets the join-threshold.
- **Independence / contrarianism** (inverse of conformity): resistance to doing
  a thing just because others are. High independence raises the join-threshold
  and shortens the stay.
- **Restlessness / curiosity** (a slice of Openness + low Conscientiousness):
  how often the character changes its mind -- wanders off, re-picks a direction,
  re-evaluates. Feeds the existing idle/jump cadence and the leave timer.

These can be derived from one or two underlying values rather than stored
independently (e.g. sociability and independence as two ends biased by one
"social pull" scalar plus noise), but keeping them as separate named scalars in
[0,1] is clearer and cheap.

### 1.3 Utility / score-based action selection -- choosing the behavior

The robust way to pick among "keep wandering," "join that nearby group," and
"leave my group" is **utility AI**: score each candidate action with a function
of the current situation, then pick the highest (or sample proportionally to
score for variety). Standard practice ([7], [8], [9], [11]):

- Each input (distance to nearest cluster, cluster size, time-in-state) is
  **normalized to [0,1]**, then passed through a **response curve** (linear,
  polynomial, logistic, etc.) that shapes how that input translates to appeal.
- A character's **traits become the curve parameters / weights**. Same world
  state, different trait values -> different winning action. This is exactly how
  one codebase produces a diverse-feeling crowd: the scoring logic is shared,
  the per-agent parameters vary.
- Scores are recomputed continuously as the world changes.

This composes cleanly with a threshold model: the join-utility is essentially
"is the nearby crowd big enough to clear my threshold, weighted by how close it
is and how sociable I am."

### 1.4 Hysteresis -- not flip-flopping every frame

The classic failure mode of any continuously-re-evaluated selector is
**oscillation**: two actions with near-equal scores swap every frame, so the
character jitters between "joining" and "wandering." The standard fixes ([7],
[10], [12]):

- **Hysteresis / dual thresholds**: use a higher score to *enter* a state than
  to *stay* in it (or a higher crowd-size to join than to leave). The gap is a
  dead-band that absorbs noise. Behavior depends on past state, not just the
  instantaneous winner.
- **Commitment timers / inertia**: once a decision is made, hold it for a
  minimum dwell time before re-evaluating. This is the same trick the codebase
  already uses for idle pauses (`_pause_timer`) and emotes (`emote_timer`).
- **Bonus-to-current-action**: add a small constant to the score of whatever the
  agent is currently doing, so it only switches when a clearly better option
  appears.

### 1.5 Deterministic, stable-but-diverse seeding

To make personalities **repeatable across sessions and process restarts** but
varied across viewers, the established technique is **hash-based seeding**: hash
a stable identifier into a number and derive traits from it, so the same input
always yields the same output regardless of order or timing ([13]). This is
*exactly* the pattern already in this repo:

```python
# twitch_playground/assets/character_defs.py
digest = hashlib.md5(username.encode("utf-8")).hexdigest()
return keys[int(digest, 16) % len(keys)]
```

`md5` is chosen deliberately over Python's salted built-in `hash()` because the
latter is not stable across runs. The personality model should reuse this exact
approach -- a viewer who is solitary today is solitary next week.

---

## 2. Concrete recommendations for this project

### 2.1 A small, seeded per-character trait model

Add a tiny pure-data trait struct, seeded deterministically from the username
the same way `assign_character` is. Keep it dependency-free and in the assets or
sim layer.

```python
# sketch only -- not committed by this ticket
@dataclass(frozen=True)
class Personality:
    sociability: float   # [0,1] -- pull toward other characters
    independence: float  # [0,1] -- resistance to following the crowd
    restlessness: float  # [0,1] -- how often it re-decides / wanders off

def personality_for(username: str) -> Personality:
    # Use a DIFFERENT salt than assign_character so trait != appearance bucket;
    # otherwise everyone who looks like "Officer Hod" also acts identically.
    digest = hashlib.md5(f"persona:{username}".encode("utf-8")).hexdigest()
    h = int(digest, 16)
    # carve independent bytes out of the digest for each axis
    sociability  = ((h >> 0)  & 0xFFFF) / 0xFFFF
    independence = ((h >> 16) & 0xFFFF) / 0xFFFF
    restlessness = ((h >> 32) & 0xFFFF) / 0xFFFF
    return Personality(sociability, independence, restlessness)
```

Notes:
- **Salt the persona hash** so it is decorrelated from the appearance hash in
  `assign_character`. Same `md5` machinery, different prefix.
- Slicing independent byte-windows out of one digest gives several
  uncorrelated [0,1] axes from a single hash -- no per-axis hashing needed.
- Optionally skew the distribution so loners are a minority: e.g. square the
  sociability draw so most characters are mildly-to-strongly social and a tail
  is genuinely solitary. The threshold-model insight ([1]) is that the
  *distribution* shape, not the mean, controls how readily crowds form -- this
  is the knob to make the room feel right.

### 2.2 How traits bias the wander / follow / leave decision

Today grouping is **purely command-driven**: `World._cmd_follow` is the only
path into `GROUPED`, and `_wander` never chooses to cluster on its own. The user
wants *autonomous* gravitation. The minimal addition is a periodic, trait-biased
**join check** inside the wandering path and a **leave check** inside the
grouped path, both expressed as utility scores with hysteresis.

**Join (while WANDER, grounded):**
Compute, from the crowd-awareness layer, the nearest cluster's size `n` and
distance `d` (only clusters on a reachable surface count). Then:

```
join_score = sociability
           * proximity_curve(d)          # 1 when close, ->0 past some radius
           * threshold_curve(n, persona) # 0 until n clears this char's threshold
           * (1 - independence)          # loners discount the social pull
```

- `threshold_curve` realizes the Granovetter idea: a per-character join count
  `T = 1 + round(independence * MAX_T)`. Sociable/low-independence chars have
  `T = 1` (join a single other character); solitary chars have a high `T` (need
  a near-mob), and the most extreme can be capped to "never auto-joins."
- Join only fires if `join_score` exceeds an **enter** threshold; commit for a
  minimum dwell time before any leave check (hysteresis 2.3). On firing, route
  through the *existing* grouping machinery -- call the equivalent of
  `World._add_to_group(self, nearest_anchor)`. No new mode, no rewrite.

**Leave (while GROUPED):**

```
leave_score = independence
            * restlessness
            * shrink_curve(n)        # grows as the cluster gets small/stale
            * dwell_curve(t_in_group)
```

Fire a `set_wander()` / `_remove_from_group` when `leave_score` clears a
**leave** threshold *and* the minimum dwell time has elapsed. Use a leave count
floor strictly below the join count `T` so the same crowd size that pulled a
character in does not immediately push them out (this is the dual-threshold
dead-band).

**Restlessness also feeds existing knobs.** `restlessness` is a natural
per-character multiplier on the current global `JUMP_CHANCE` / `IDLE_CHANCE`
constants and on how often a wanderer re-picks `_facing`. That alone --
before any grouping logic -- already makes the crowd visibly varied: some
characters pace constantly, others stand still for long stretches.

### 2.3 How this layers onto the existing `Mode` state machine (no rewrite)

The current FSM stays exactly as-is: `WANDER`, `GROUPED`, `EMOTING`, with the
same transitions. The personality layer is **additive**:

1. `Character.__init__` gains a `self.persona = personality_for(username)`
   (or it is passed in by `World.spawn`, mirroring how `sprites` and
   `nameplate` are injected today -- keeps `Character` testable).
2. In `_wander`, after the existing jump/idle-pause logic, add a low-frequency
   join check (gate it behind a `self._decide_timer` countdown so it runs a few
   times per second, not every frame -- cheap, and a natural hysteresis point).
   If it fires, transition into the *existing* grouped flow.
3. In the grouped path, add the symmetric leave check behind the same timer.
4. Multiply `JUMP_CHANCE` / `IDLE_CHANCE` / facing re-rolls by `restlessness`
   where they are read.

Why this is safe:
- **Explicit chat commands stay authoritative.** A `!follow` / `!leave` / `!join`
  from the viewer should override and (briefly) suppress the autonomous check --
  e.g. set a "manual hold" timer on `touch()` so the AI does not immediately
  undo a viewer's command. The viewer's intent always wins; autonomy only fills
  the silence.
- The decision logic is **pure and trait-parameterized**, so it belongs next to
  `steering.separation_push` as testable functions over scalars/vectors.
- Nothing about rendering, the clip state machine, platforms, or grouping slot
  arrangement changes. `_arrange_group` already handles N members fanning out.

### 2.4 Tuning / gotchas to expect

- **Decorrelate the persona seed from the appearance seed** (2.1) or all
  same-looking characters behave identically -- the room reads as cloned.
- **Skew the trait distribution**, do not draw uniform. A handful of true loners
  and a sea of joiners reads better than a 50/50 split, and the threshold-model
  literature ([1], [3]) says the distribution shape is what determines whether
  clusters form at all.
- **Hysteresis is mandatory**, not optional polish. Without the dual
  join/leave thresholds plus a dwell timer, characters on a crowd-size boundary
  will visibly vibrate between joining and leaving ([10], [12]).
- **Keep the decision cadence low** (a few Hz via a countdown timer). It is
  cheaper and doubles as oscillation damping.
- **Reachability matters.** A "nearby" cluster on a different platform tier is
  not actually joinable without a jump path; the join check should only count
  clusters the crowd-awareness layer marks as reachable, or the character will
  walk into a wall under its slot.

---

## 3. Sources

1. Granovetter, M. "Threshold Models of Collective Behavior." (overview / PDF)
   https://www.academia.edu/2312720/Granovetter_s_Threshold_Models_of_Collective_Behaviour
2. "A network-based microfoundation of Granovetter's threshold model for social
   tipping." Scientific Reports (2020).
   https://www.nature.com/articles/s41598-020-67102-6
3. "Threshold Models of Collective Behavior II: The Predictability Paradox and
   Spontaneous Instigation." Sociological Science (2020).
   https://sociologicalscience.com/download/vol-7/december/SocSci_v7_628to648.pdf
4. "Big Five personality traits." Wikipedia.
   https://en.wikipedia.org/wiki/Big_Five_personality_traits
5. "Big Five Personality Traits: The 5-Factor Model of Personality." SimplyPsychology.
   https://www.simplypsychology.org/big-five-personality.html
6. "Big Five Personality Traits: The OCEAN Model Explained." Yu-kai Chou.
   https://yukaichou.com/behavioral-analysis/big-five-personality-ocean-traits-costa-mccrae/
7. Aversa, D. "Utility-based AI for Games."
   https://www.davideaversa.it/blog/utility-based-ai/
8. Lewis, M. "Choosing Effective Utility-Based Considerations." Game AI Pro 3, ch. 13.
   http://www.gameaipro.com/GameAIPro3/GameAIPro3_Chapter13_Choosing_Effective_Utility-Based_Considerations.pdf
9. "Utility system." Wikipedia.
   https://en.wikipedia.org/wiki/Utility_system
10. "AI - State Machines Introduction" (hysteresis to damp state oscillation).
    Newcastle University.
    https://research.ncl.ac.uk/game/mastersdegree/gametechnologies/aitutorials/1state-basedai/AI%20-%20State%20Machines.pdf
11. "Considerations / Response Curves." Infinite Axis Utility System docs.
    https://uintel-go.utilityworlds.com/Documentation/UtilityIntelligence/Considerations/
12. "Addressing Action Oscillations through Learning Policy Inertia." arXiv:2103.02287.
    https://arxiv.org/pdf/2103.02287
13. "Noise and Procedural Library" (hash-seeded per-entity determinism, FNV-1a /
    coordinate hashing for reproducible per-entity traits).
    https://deepwiki.com/vulpeslab/hytale-docs/7.2-noise-and-procedural-library
