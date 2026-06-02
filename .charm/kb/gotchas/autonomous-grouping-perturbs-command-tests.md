---
id: autonomous-grouping-perturbs-command-tests
root: gotchas
type: gotcha
status: current
summary: "World.update runs the L4 autonomous join/leave layer every frame, so command-only tests must set settings.AUTONOMOUS_GROUPING=False or spawned characters' random personas can auto-form/dissolve clusters and flip their assertions."
created: 2026-06-01
updated: 2026-06-01
---

# Autonomous grouping perturbs command-only tests

L4 (T-028) added an autonomous join/leave layer that `World.update` runs every
frame (`World._tick_autonomy`), driven by each character's md5-seeded
`Personality`. With the default `settings.AUTONOMOUS_GROUPING = True`, a freshly
`spawn`ed character gets a *random* persona, and two sociable wanderers who land
near each other on the same surface will **form a cluster on their own** within a
few seconds -- or a restless loner will peel out of one.

That breaks any test that asserts command-only grouping outcomes (e.g. "after
`!hug` both are back to `WANDER`", "the follower stands exactly beside the
anchor"): the autonomous layer can group/ungroup characters underneath the
assertion, and because spawn x is random the failure is intermittent.

Fix: command-path tests must disable the layer. `test_world.py` has a
`no_autonomy` fixture (`monkeypatch.setattr(settings, "AUTONOMOUS_GROUPING", False)`)
applied to the four command tests. Tests that *do* exercise autonomy instead
pin positions, freeze wander drift (`WANDER_DISPLACE`/`WANDER_REORIENT_CHANCE` to
0), set explicit personas, and force `char._decide_timer = 0`.

Note `Character.update` alone does NOT trigger autonomy -- only `World.update`
does -- so `test_character.py` physics tests are unaffected and need no opt-out.
See [agent-behavior-model](../architecture/agent-behavior-model.md) L4 and
[grouped-walk-to-slot-time-is-unbounded](grouped-walk-to-slot-time-is-unbounded.md)
(the related "pin positions / loop enough frames" discipline).
