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
