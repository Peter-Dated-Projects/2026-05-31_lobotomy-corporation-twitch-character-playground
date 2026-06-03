---
id: autonomous-grouping-perturbs-command-tests
root: gotchas
type: gotcha
status: current
summary: "World.update runs the L4 autonomous join/leave layer every frame; as of T-033 the settings.AUTONOMOUS_GROUPING default is FALSE, so the polarity is inverted -- command tests get protection for free, but tests that exercise autonomy must opt IN via monkeypatch."
created: 2026-06-01
updated: 2026-06-02
---

# Autonomous grouping perturbs command-only tests

L4 (T-028) added an autonomous join/leave layer that `World.update` runs every
frame (`World._tick_autonomy`), driven by each character's md5-seeded
`Personality`. When the layer is on, a freshly `spawn`ed character gets a
*random* persona, and two sociable wanderers who land near each other on the same
surface will **form a cluster on their own** within a few seconds -- or a restless
loner will peel out of one.

That breaks any test that asserts command-only grouping outcomes (e.g. "after
`!hug` both are back to `WANDER`", "the follower stands exactly beside the
anchor"): the autonomous layer can group/ungroup characters underneath the
assertion, and because spawn x is random the failure is intermittent.

**T-033 flipped the default to `settings.AUTONOMOUS_GROUPING = False`** (the crowd
was clumping/freezing; suppressing self-formed clusters keeps it wandering --
explicit `!follow` still groups). This inverts the testing discipline:

- **Command-path tests** now get protection from the default and no longer
  strictly need to opt out -- but `test_world.py` still has a `no_autonomy`
  fixture (`monkeypatch.setattr(settings, "AUTONOMOUS_GROUPING", False)`) that
  makes the intent explicit and is robust to anyone re-flipping the default.
- **Tests that exercise the autonomy layer itself** must now opt IN with
  `monkeypatch.setattr(settings, "AUTONOMOUS_GROUPING", True)` at the top
  (`test_autonomous_join_forms_a_cluster`,
  `test_autonomous_leave_when_restless_loner_in_small_cluster`), then pin
  positions, freeze wander drift (`WANDER_DISPLACE`/`WANDER_REORIENT_CHANCE` to
  0), set explicit personas, and force `char._decide_timer = 0`.

Note `Character.update` alone does NOT trigger autonomy -- only `World.update`
does -- so `test_character.py` physics tests are unaffected and need no opt-out.
See [agent-behavior-model](../architecture/agent-behavior-model.md) L4 and
[grouped-walk-to-slot-time-is-unbounded](grouped-walk-to-slot-time-is-unbounded.md)
(the related "pin positions / loop enough frames" discipline).
