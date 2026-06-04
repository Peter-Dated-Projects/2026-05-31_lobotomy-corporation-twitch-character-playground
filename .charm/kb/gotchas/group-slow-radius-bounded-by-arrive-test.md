---
id: group-slow-radius-bounded-by-arrive-test
root: gotchas
type: gotcha
status: current
summary: "GROUPED arrive easing (T-026) added a GROUP_SLOW_RADIUS deceleration zone before the GROUP_ARRIVE_RADIUS snap; the radius is tuned small (28px) on purpose because test_world's arrival test loops a fixed 240 frames -- inside the slow zone desired speed scales linearly to ~0, so a large radius makes the exponential approach tail blow that frame budget."
created: 2026-06-01
updated: 2026-06-01
---

`Character._move_toward_slot` now eases a GROUPED follower into its slot: outside
`GROUP_SLOW_RADIUS` it steers toward `WALK_SPEED`, inside it scales the desired
speed down linearly with distance, and `GROUP_ARRIVE_RADIUS` (4px) is still the
final settle/snap. Velocity itself also eases (capped by `MAX_FORCE`), so the
follower decelerates rather than running flat-out then teleporting.

The trap: inside the slow zone the approach is roughly exponential
(desired speed proportional to remaining distance), so the closing time grows as
the radius grows. `tests/test_world.py::test_follow_snaps_follower_beside_leader`
pins the follower ~70px from the slot and loops a fixed **240 frames at 1/60s**
(4s) before asserting `distance <= 1.0`. With `GROUP_SLOW_RADIUS = 28.0` the
follower covers the open stretch at full speed and only decelerates over the last
28px, settling well inside the budget. Bumping the radius to, say, 80px stretches
the deceleration tail and can break that assertion even though the behavior is
"more correct."

If you widen `GROUP_SLOW_RADIUS` for feel, re-run `test_world.py` and either keep
it modest or lift the frame budget in that test. Related background:
[grouped-walk-to-slot-time-is-unbounded](grouped-walk-to-slot-time-is-unbounded.md)
(arrival time already scales with spawn separation; easing lengthens only the
final tail).

Aside on naming: the research/ticket referred to the acceleration cap as
"WALK_ACCEL/MAX_FORCE" -- it is implemented as a single `settings.MAX_FORCE`
(px/s^2) knob, not two constants, to avoid a dead duplicate.
