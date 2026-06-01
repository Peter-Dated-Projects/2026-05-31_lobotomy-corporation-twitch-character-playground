---
id: group-slot-y-must-match-a-platform-top
root: gotchas
type: gotcha
status: current
summary: "Follow-group slots are split across two tracks: World sets group_slot.y to a platform.top; Character resolves which platform from that y -- a slot.y off any platform top leaves the follower unable to snap/ground."
created: 2026-06-01
updated: 2026-06-01
---

Follow grouping is a two-track handshake, and the seam is `group_slot.y`:

- `World._arrange_group` (sim/world.py) computes each follower's slot with
  `slot.y = leader.platform.top` and `slot.x` clamped to that platform's
  `[left, right]` span. The anchor (members[0]) keeps its own `pos` as its slot
  so it stays put.
- `Character._move_toward_slot` / `set_grouped` (sim/character.py) then resolve
  which platform the slot belongs to via `_surface_at(slot.x, slot.y)`, which
  matches a platform top **within a small tolerance**.

Footgun: if World ever produces a `slot.y` that does not equal some platform's
`top` (e.g. you anchor a slot to the leader's *feet* while the leader is mid-jump,
or you nudge slot.y for spacing), `_surface_at` returns None and the follower
never grounds on the cluster -- it reads as a follower stuck off-surface. That is
why `_arrange_group` guards `leader.platform is None` (airborne leader) by falling
back to the anchor's current feet-y and screen margins instead of inventing a
y that no platform shares.

Related: the "hug freeze" / "leave doesn't dissolve" bug class is avoided because
`Character.set_wander` rewrites `_prev_mode = WANDER` even while EMOTING -- so a
character hugged and then dropped from a dissolving cluster reverts to WANDER, not
to a slotless GROUPED state that would stand frozen.
