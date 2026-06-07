---
id: speak-overlay-cleared-by-polling-not-callback
root: gotchas
type: gotcha
status: current
summary: "World is main-thread-only, so the speak overlay (active_speaker) must be cleared by polling SpeakEngine.is_speaking from the loop (World.tick_speak), NOT from the engine's background on_done callback."
created: 2026-06-07
updated: 2026-06-07
---

The speak feature shows a robot + balloon overlay while a `!say` utterance plays.
The overlay state (`World.active_speaker`) is set on the main thread in `_cmd_say`
and must also be *cleared* on the main thread.

`SpeakEngine.speak(text, character, on_done=...)` runs synthesis + playback on a
daemon thread and fires `on_done` when playback ends -- but that callback runs on
the engine's background thread. `World` is documented as main-thread-only (commands
arrive via a thread-safe queue, no locking anywhere), so clearing `active_speaker`
from `on_done` would be an off-thread mutation / data race.

The wiring (T-008) instead clears it by polling: `World.tick_speak()` runs every
frame in the main loop and sets `active_speaker = None` once `engine.is_speaking`
goes False. This is safe because `speak()` flips `is_speaking` True *synchronously*
before returning, so there is no frame where we set the overlay and immediately
clear it. If you ever switch to the callback to clear it, you must add locking or
hand the clear back to the main thread via the command queue.

Related: the v0 overlap policy is ignore-if-busy -- a second `!say` while one is
playing is dropped in `_cmd_say` (a queue can replace this later).
