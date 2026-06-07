---
id: espeak-data-path-length-limit
root: gotchas
type: gotcha
status: current
summary: "espeak-ng truncates its data path at an internal ~160-char buffer, so the deeply-nested bundled espeak-ng-data path silently fails; pass kokoro_onnx EspeakConfig(data_path=<short copy>) so Kokoro's Tokenizer uses a short path."
created: 2026-06-07
updated: 2026-06-07
---

The speak feature's Kokoro TTS phonemizes English through espeak-ng (via
`espeakng_loader` + `phonemizer-fork`). espeak-ng stores its data directory in
a fixed-size internal buffer (`N_PATH_HOME`, ~160 chars). When the path to the
bundled `espeak-ng-data` exceeds that, espeak silently ignores it and falls back
to the compiled-in build default (a CI path like
`/Users/runner/work/espeakng-loader/.../espeak-ng-data/phontab`) which does not
exist, so synthesis dies with:

    Error processing file '/Users/runner/work/.../espeak-ng-data/phontab': No such file or directory.

This bites whenever the venv lives under a long directory. This repo's path
(`.../2026-05-31_lobotomy-corporation-twitch-character-playground/.venv/.../espeakng_loader/espeak-ng-data`)
is 161 chars -> over the limit -> fails. The KokoClone spike at `/tmp/kokoclone-spike`
worked only because its path was 86 chars. It will also bite the Windows
deployment box (long repo path under the user profile).

Things that do NOT fix it:
- `espeakng_loader.make_library_available()` / `EspeakWrapper.set_data_path()`
  before synth -- Kokoro's `Tokenizer.__init__` resets the data path to the long
  bundled location when `Kokoro(...)` is constructed, overriding earlier calls.
- A **symlink** to a short path -- espeak resolves the data path to its real
  location, so the symlink expands back to the long target and truncates again.

The fix (in `twitch_playground/speak/_kokoclone.py`): copy `espeak-ng-data` to a
short real directory under the temp dir (one-time, ~30 MB) and pass that via
`kokoro_onnx.EspeakConfig(data_path=<short>)` to `Kokoro(...)`. EspeakConfig is
the only override Kokoro's Tokenizer honors, because the Tokenizer itself calls
`EspeakWrapper.set_data_path(espeak_config.data_path)`.
