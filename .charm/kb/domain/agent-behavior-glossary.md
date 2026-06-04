---
id: agent-behavior-glossary
root: domain
type: domain
status: current
summary: "Definitions of the agent-behavior terms used in the five-layer design — steering forces, max_force vs max_speed, wander, arrive, the three boids rules, density, the personality traits, join/leave thresholds, hysteresis, and the emotion model."
related:
  - architecture/agent-behavior-model
  - decisions/0004-layered-agent-behavior
created: 2026-06-01
updated: 2026-06-01
---

# Agent Behavior Glossary

Terms used by the [agent-behavior-model](../architecture/agent-behavior-model.md)
and [0004-layered-agent-behavior](../decisions/0004-layered-agent-behavior.md).
In our world everything is the **horizontal (x)** scalar version of the textbook
2D concept — agents are pinned to platform surfaces.

## Steering core

- **Steering force** — the correction applied each frame to turn current motion
  into desired motion: `steering = desired_velocity - current_velocity`, clamped
  and integrated. Produces acceleration with weight instead of teleporting
  velocity.
- **max_speed** — cap on the velocity magnitude; the character's top walking
  speed. (Constant exists in `settings.py`, currently unused.)
- **max_force** — cap on the steering force per step; how *sharply* a character
  can change direction or speed. Small = heavy/lumbering, large = twitchy. Distinct
  from max_speed: one limits how fast you go, the other how fast you change.
- **Wander heading** — a persistent per-character desired heading that drifts by a
  small random delta each frame rather than being re-rolled, giving coherent
  meandering (long-term drift, short-term stability) instead of coin-flip jitter.
- **Arrive radius / slow radius** — Reynolds "arrive": inside a slowing radius the
  desired speed scales linearly down to 0 so the character decelerates to a
  graceful stop instead of full-speed-then-snap. Our `GROUP_ARRIVE_RADIUS` is the
  final settle; a larger `GROUP_SLOW_RADIUS` would start the deceleration.

## Crowd awareness (boids rules)

- **Separation** — short-range repulsion away from neighbors that crowd you;
  grows as they get closer. The one rule we already have (`separation_push`).
- **Cohesion** — attraction toward the average position (center of mass) of local
  neighbors; pulls stragglers back into the pack.
- **Alignment** — steering toward the average heading/velocity of local neighbors;
  makes a knot of characters drift together. Needs neighbor headings, not just
  positions.
- **Local density** — the same-band neighbor count, free from the shared neighbor
  scan; used to slow movement, suppress hops, and bias idle-pausing in crowds.

## Personality traits (seeded [0,1] scalars)

- **Sociability** — how strongly a character is drawn to others; the primary axis,
  sets the join threshold low.
- **Independence** — resistance to following the crowd; raises the join threshold
  and shortens stays.
- **Restlessness** — how often a character re-decides / wanders off; multiplies
  jump/idle cadence and feeds the leave timer.

## Following decisions

- **Join / leave threshold** — the per-character crowd size that must be present
  before the agent autonomously joins (Granovetter threshold model): sociable
  chars join a single neighbor, loners need a near-mob. A symmetric, lower
  leave-threshold governs peeling off.
- **Hysteresis** — using a higher bar to *enter* a state than to *stay* in it (dual
  thresholds), creating a dead-band that absorbs noise so the agent doesn't
  flip-flop between joining and leaving every frame.
- **Dwell (commitment timer)** — a minimum time a decision is held before
  re-evaluation; the second oscillation-damper alongside hysteresis.

## Emotion

- **Valence** — the pleasant-to-unpleasant axis, [-1, 1]. Drives approach vs
  withdraw and (with arousal) the face. Low valence damps movement speed.
- **Arousal** — the calm-to-excited axis, [0, 1]. Drives movement speed and
  restlessness, and is bumped by crowding.
- **Emotional contagion** — one agent's emotion spreading to nearby agents: each
  frame a character's emotion is nudged toward the proximity-weighted average of
  its neighbors'. The lag as it ripples outward is the desired effect, not a bug.
- **Expressiveness** — how strongly a character *sends* its emotion to others (the
  sender side of contagion).
- **Susceptibility** — how strongly a character *receives* neighbors' emotion (the
  receiver side). Together these per-agent knobs make some characters calm anchors
  and others panic amplifiers.
