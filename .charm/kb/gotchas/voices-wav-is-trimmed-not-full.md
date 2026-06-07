---
id: voices-wav-is-trimmed-not-full
root: gotchas
type: gotcha
status: current
summary: "setup_voices.py writes TWO files per character -- voices/<name>.wav is a short ~15s trimmed VC reference (what the engine reads), voices/<name>.full.wav is the long raw concat; do not point the engine at the .full.wav."
created: 2026-06-07
updated: 2026-06-07
---

`scripts/setup_voices.py` no longer leaves the 8-11min concatenated dub audio at
`voices/<name>.wav`. As of T-006 it writes two files into the gitignored
`twitch_playground/assets/voices/` dir:

- `<name>.wav` -- a short (~15s) trimmed, optionally denoised clip. **This is the
  reference the KokoClone/Kanade VC engine reads on every utterance.** Keep the
  engine pointed here; a short clean clip is a better VC target than a long one
  carrying background score (per the voice-cloning research).
- `<name>.full.wav` -- the full concatenated dub audio, kept only so the clip can
  be re-trimmed later without re-downloading.

The trim is a deterministic energy heuristic (no VAD/model): 0.5s-frame RMS, mark
a frame voiced when RMS > 40% of the clip's 90th-percentile frame RMS, slide a
15s window past a 5s intro skip, pick the window with the most summed voiced
energy. It reliably lands on sustained speech for these dub clips but is loudness-
based, not speech-aware -- if a clip's loudest sustained region were music it
could mis-pick. To re-tune, edit `TARGET_SECONDS` / `INTRO_SKIP_SECONDS` /
`VOICED_FRACTION` near the top of the script.

`--force` rebuilds both files; `--denoise` runs deepfilternet on the SHORT clip,
not the full one. Idempotency key is the existence of `<name>.wav`.
