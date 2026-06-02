---
id: grid-cell-invariant-and-density-ceiling
root: gotchas
type: gotcha
status: current
summary: "World.update's 1D neighbour grid is correct only while GRID_CELL >= every interaction radius (own cell +/-1 must capture all reachable neighbours); GRID_CELL is defined after CONTAGION_RADIUS in settings.py for that reason, and the speedup is density-bounded (~3x at uniform max density on the fixed 960px screen)."
created: 2026-06-01
updated: 2026-06-01
---

T-030 replaced the O(N^2) per-frame neighbour scan with a 1D horizontal bucket
grid (`_bucket_by_cell` / `_candidates_for` in `sim/world.py`). Two non-obvious
constraints:

**1. The cell-size correctness invariant.** Each character is handed only its own
cell plus the two adjacent cells (`floor(x / GRID_CELL) +/- 1`). This loses no
neighbour ONLY because `GRID_CELL >= the largest interaction radius` any rule
uses: with that, any neighbour within radius R (<= cell) of a character at x lies
in `[x-R, x+R]`, which spans at most one cell on either side. `GRID_CELL` is
derived as `max(HSEP_RADIUS, CROWD_COH_RADIUS, CROWD_ALI_RADIUS,
CROWD_DENSITY_RADIUS, CONTAGION_RADIUS)` so retuning any radius keeps it correct
automatically. If you ever add a rule with a wider radius, add it to that `max()`
or the grid will silently drop neighbours. Note `CONTAGION_RADIUS` uses Euclidean
distance, but Euclidean <= R implies horizontal <= R, so the horizontal cell still
captures it.

**2. Import-order trap in settings.py.** `GRID_CELL` references `CONTAGION_RADIUS`,
which is defined in the Emotion block lower in the file. So `GRID_CELL` MUST be
defined *after* that block (it sits just before the command-impulse constants),
not up with the HSEP_/CROWD_ block where the other radii live. Moving it up gives
a `NameError` at import.

**3. The speedup is bounded by density, not N.** Benchmarked (fair brute baseline,
same code, uniform layout across all four tiers): N=200 23.2->7.4ms, N=400
90.6->27.4ms, N=800 361->106ms -- a flat ~3.1-3.4x. The ceiling is geometric: all
characters share one fixed 960px screen, so the grid only ever has ~12 cells, and
at uniform max density a +/-1 slice still holds ~1/4 of everyone. The real win is
asymptotic (cost now scales with LOCAL density, and empty cells cost nothing, so
clustered/sparse layouts win far more) and budget-relevant: within the 83ms/12fps
frame budget the practical cap rises from ~380 (brute) to ~700 (grid). Do not
expect a 1D grid to give order-of-magnitude wins while the whole crowd is packed
into one screen width -- that density is inherent to the interaction, not the
data structure.
