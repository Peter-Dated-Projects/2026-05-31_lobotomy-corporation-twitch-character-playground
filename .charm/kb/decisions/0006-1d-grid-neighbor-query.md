---
id: 0006-1d-grid-neighbor-query
root: decisions
type: decision
status: current
related: 0004-layered-agent-behavior, grid-cell-invariant-and-density-ceiling
created: 2026-06-01
updated: 2026-06-01
---

# 1D horizontal bucket grid for the per-frame neighbour query

## Context

Decision 0004 deliberately shipped brute-force O(N^2) neighbour scanning, because
at the original `MAX_CHARACTERS = 100` it was simpler and faster-in-practice than a
grid (the crowd-research doc, section 2.5, explicitly recommended deferring spatial
acceleration with the trigger "when we raise the cap or profiling shows the loop
hot"). T-030 hit that trigger: the per-frame interaction was the wall on crowd
size (~90ms at N=400, exceeding the 83ms/12fps budget; render is negligible).

## Decision

Replace the full-list scan with the **1D horizontal bucket grid** section 2.5
specced. Motion is surface-bound and ~1D-per-surface, so a 2D grid is unnecessary:
`World.update` buckets the frame's shared `Neighbor` records by
`floor(pos.x / GRID_CELL)` once, then hands each character only its own cell +/- 1
as candidates. `GRID_CELL` is sized to the largest interaction radius so the
candidate slice is provably a superset of every reachable neighbour -- the steering
math and the `Neighbor` record are completely unchanged, only the candidate set
shrinks.

This supersedes the *performance* clause of 0004 (brute-force neighbours); the
other four layers of 0004 stand.

## Why this over the alternatives

- **2D uniform grid / spatial hash:** unnecessary. Vertical extent is four discrete
  tiers ~95px apart and rules are same-band; a 1D grid over x captures the
  structure with a fraction of the bookkeeping.
- **numpy vectorization of the distance comparisons:** the doc's cheaper fallback,
  but it keeps O(N^2) asymptotics (just a smaller constant) and would push the
  steering rules out of plain-Python pure functions. The grid changes the
  asymptotics and leaves the rules untouched.

## Consequence / known limit

Fair benchmark (uniform layout): ~3.1-3.4x across N=200/400/800. The win is bounded
by density on the fixed 960px screen, not by N -- see
[[grid-cell-invariant-and-density-ceiling]] for the cell-size correctness invariant
and why the speedup plateaus at ~3x under uniform max density. The lower-frequency
autonomous-join scan (`World._join_candidate`, ~2.5Hz) is still O(N^2) and was left
untouched as out of scope; it is the next candidate if the cap rises much further.
