# Gotchas

Traps, flaky behavior, and non-obvious constraints -- the things that bite you twice.

_No notes yet. Add atomic notes in this directory and list each one in the table below
(see `../CONTRIBUTING.md`)._

| Note | Summary | Status |
|---|---|---|
| [group-slot-y-must-match-a-platform-top](group-slot-y-must-match-a-platform-top.md) | Follow slots split across tracks: World sets slot.y to a platform.top, Character resolves the platform from that y; a slot.y off any platform top leaves the follower unable to snap/ground. | current |
| [character-surface-binding](character-surface-binding.md) | A Character treats platform is None as airborne (plays the jump clip and falls); to place one ON a surface its feet pos.y must equal a platform top within 1px so the first update can bind it. | current |
| [grouped-walk-to-slot-time-is-unbounded](grouped-walk-to-slot-time-is-unbounded.md) | A GROUPED follower walks to its slot at WALK_SPEED (no teleport), so arrival time scales with spawn separation (~15s worst case); tests waiting for arrival must pin positions or loop enough frames. | current |
| [no-graphics-import-test-needs-subprocess](no-graphics-import-test-needs-subprocess.md) | Asserting a module doesn't import pygame/PIL via sys.modules fails in-process because conftest.py imports pygame session-wide; run the import check in a fresh subprocess instead. | current |
| [calibrate-variant-indices-out-of-range](calibrate-variant-indices-out-of-range.md) | Half the named characters' `# calibrate` face/hair variant indices exceed what extraction yields, so they silently render as placeholder art via LobCorpProvider's per-character fallback; fix is a one-time index calibration pass in character_defs.py. | current |
| [layer-scale-template-generalizes](layer-scale-template-generalizes.md) | The single LAYER_SCALES/LAYER_OFFSETS template calibrated for Standard Agent renders all 10 characters as recognizable chibis, because each layer type comes from one shared sheet at a consistent native size; only hair vertical offset varies enough to warrant per-character nudging. | current |
| [facing-tracked-but-sprite-never-flipped](facing-tracked-but-sprite-never-flipped.md) | RESOLVED (T-026): Character now exposes a deadzoned public facing and render/scene.py flips the sprite when facing<0; kept for history, do not re-report. | resolved |
| [group-slow-radius-bounded-by-arrive-test](group-slow-radius-bounded-by-arrive-test.md) | GROUPED arrive easing (T-026) adds a GROUP_SLOW_RADIUS deceleration zone before the snap; it is tuned small (28px) because test_world's arrival test loops a fixed 240 frames and a large radius stretches the exponential approach tail past that budget. | current |
| [shared-neighbor-list-includes-self](shared-neighbor-list-includes-self.md) | World.update builds ONE neighbour-record list per frame that includes every character (the agent itself too) as a frame-start snapshot; every steering rule must skip self via a `0 < dist` test, and the records are decoupled copies, not live references. | current |
| [autonomous-grouping-perturbs-command-tests](autonomous-grouping-perturbs-command-tests.md) | World.update runs the L4 autonomous join/leave layer every frame, so command-only tests must set settings.AUTONOMOUS_GROUPING=False or spawned characters' random personas can auto-form/dissolve clusters and flip their assertions. | current |
