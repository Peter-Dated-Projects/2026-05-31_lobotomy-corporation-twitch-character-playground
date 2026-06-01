---
id: grouped-walk-to-slot-time-is-unbounded
root: gotchas
type: gotcha
status: current
summary: "A GROUPED follower walks to its slot at WALK_SPEED with no teleport, so arrival time scales with spawn separation (~900px worst case = ~15s); tests that wait for arrival must pin positions or loop enough frames, not assume a fixed count."
created: 2026-06-01
updated: 2026-06-01
---

`Character._move_toward_slot` (sim/character.py) moves a GROUPED follower toward
`group_slot` at `WALK_SPEED` (60 px/s), one `dt` step at a time -- there is no
snap/teleport to the slot on `!follow`. Only the leader (anchor) lands on its
slot immediately, because the anchor's slot **is** its current pos.

Consequences:

- A follower spawned far from its leader can take a long time to arrive. World
  spawns at a random x in `[WALL_MARGIN, SCREEN_W - WALL_MARGIN]`, so worst-case
  separation is ~888px = ~15s of sim time = ~900 frames at dt=1/60. A test that
  asserts "follower reached its slot" after a fixed, smaller loop will pass or
  fail depending on the random spawn -- a real flaky-test trap. Fix: pin the two
  characters' x explicitly before `!follow`, or loop enough frames for the
  max separation. tests/test_world.py pins positions.

- `_move_toward_slot` sets `pos` directly and does NOT call
  `_apply_horizontal_bounds`, so a slot outside the wander band
  `[WALL_MARGIN, SCREEN_W - WALL_MARGIN]` is still reachable. `World._arrange_group`
  clamps slot.x only to the platform's `[left, right]` span (the ground spans the
  full screen, 0..SCREEN_W), so a slot can legitimately sit in the 0..WALL_MARGIN
  or (SCREEN_W-WALL_MARGIN)..SCREEN_W gutter -- reachable when GROUPED, but a
  wandering character could never stroll there. Don't assert a grouped follower
  stays inside the wander band.

Related: [[group-slot-y-must-match-a-platform-top]],
[[character-surface-binding]].
