---
id: shared-neighbor-list-includes-self
root: gotchas
type: gotcha
status: current
summary: "World.update builds ONE neighbour-record list per frame that includes every character (the agent itself too) as a frame-start snapshot; every steering rule must skip self via a `0 < dist` test, and the records are decoupled copies, not live references."
created: 2026-06-01
updated: 2026-06-01
---

# The shared neighbour-record list includes the agent itself

`World.update` (T-027) builds **one** `list[steering.Neighbor]` per frame and
hands the *same* list to every `Character.update`. Two non-obvious properties a
future rule author must respect:

1. **It includes the agent's own record.** The list is built over
   `self.characters.values()` with no per-agent exclusion (that would mean N
   list-builds, defeating the single-scan goal the crowd brief calls for). So
   every steering rule fed from it -- `separation_push`, `cohesion_pull`,
   `alignment_nudge`, `local_density` -- relies on a `0 < dist` (i.e.
   `0 < abs(other.pos.x - pos.x)`) test to skip its own zero-distance record.
   **Add a new rule and forget this and the agent counts/pulls toward itself.**
   Caveat: two genuinely overlapping characters (dist exactly 0) are also
   skipped, which is harmless at our scale but is not literally "skip self by
   identity."

2. **The records are frame-start snapshots, not live references.** `pos` is a
   `Vector2(c.pos)` *copy* (facing/vx are immutable scalars), so a rule never
   sees a neighbour that already moved this frame. This is a deliberate change
   from the old `positions = [c.pos for ...]`, which stored live `Vector2`
   refs and let later-updated characters see earlier ones' new positions (a
   frame-ordering artifact). Snapshotting gives every rule a consistent
   frame-start view; don't "optimize" the copy away.

Later behaviour layers (L4 personality, L5 emotion) widen `Neighbor` with more
fields but keep the single-build, includes-self, snapshot contract.
