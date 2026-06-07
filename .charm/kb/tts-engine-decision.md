# TTS Engine Decision: voice-clone speak feature

## DECISION (2026-06-07): KokoClone (Kokoro + Kanade VC)

Chosen after spiking both KokoClone and XTTS v2 on the same hod reference clip
and A/B listening to the outputs:

- **Quality:** the KokoClone clone was clearly preferred over XTTS v2 by ear.
- **License:** the full KokoClone stack is commercial-safe (verified below),
  unlike XTTS v2 whose weights are non-commercial.

XTTS v2 is rejected. Chatterbox/Zonos remain noted alternatives but are not
needed -- KokoClone wins on quality and is already permissively licensed.

### License verification (the whole stack is commercial-OK)

| Component | License | Source |
|---|---|---|
| Kokoro (TTS front-end + ONNX weights) | Apache 2.0 | hexgrad/Kokoro |
| Kanade tokenizer (the voice-conversion model + code) | **MIT** | frothywater/kanade-12.5hz + kanade-tokenizer (trained on LibriTTS) |
| KokoClone (glue) | Apache 2.0 | Ashish-Patnaik/kokoclone |

No non-commercial clause anywhere in the chain. Safe for a monetized stream.

### Open items before/at build

- GPU latency on the RTX 5070Ti still unverified (Mac CPU was RTF ~1.4x; see
  table below). Confirm it clears real-time on the actual streaming PC.
- The reference WAVs are 8-11 min raw dub audio with background score; trim to a
  short clean segment (~10-15s) and denoise per character for a better VC target.

---

Consolidated spike results comparing voice-clone engines for the channel-points
"speak through a robot" feature. Supersedes the engine recommendation in
`voice-cloning-research.md` (which predates the runtime spikes).

All latency numbers below are **Apple Silicon Mac, CPU only** (no CUDA; XTTS/
coqui MPS support is unreliable so torch fell back to CPU). These are a
**worst-case floor**, not the deployment target. The real stream runs on a
Windows PC with an RTX 5070Ti (CUDA), where both engines are expected to be
well under real-time. The binding latency test must be re-run on that GPU box.

## Spike comparison (measured 2026-06-07, Mac CPU)

| Engine | License | Commercial OK | Architecture | Steady-state (Mac CPU) | RTF |
|---|---|---|---|---|---|
| **XTTS v2** (coqui-tts / Idiap fork) | Coqui Public Model License | **NO** | single-model zero-shot clone | ~11.0s for 5.74s audio | ~1.9x |
| **KokoClone** (Kokoro + Kanade VC) | Apache 2.0 + Kanade | check Kanade | TTS preset voice -> per-utterance voice conversion | ~8.5s for 6.0s audio | ~1.4x |

Both are slower than real-time on Mac CPU -> **neither is viable for local dev
playback on this Mac**; develop against pre-rendered clips or accept the lag.
Both should clear real-time comfortably on the 5070Ti (unverified).

Sample artifacts for A/B listening (gitignored,
`twitch_playground/assets/voices/_spike/`):
- `hod_reference.wav` - the target voice (12s trimmed dub clip)
- `hod_xtts_sample.wav` - XTTS v2 clone of the same line
- `hod_cloned_sample.wav` - KokoClone clone of the same line

## The license problem (XTTS v2)

XTTS v2's **model weights** are under the Coqui Public Model License (CPML),
which is **non-commercial only**. Verified from the license text:

- "This license allows only non-commercial use of a machine learning model and its outputs."
- "Use for revenue-generating activity ... is not a non-commercial purpose."
- Bars any use where you "receive any direct or indirect payment arising from the use of the model or its output."

The coqui-tts *source code* is MPL-2.0 (permissive), but that does not cover the
*weights*. Coqui sold a commercial license (~$365/yr for <$1M revenue) but **shut
down (Dec 2025), so there is no longer any way to obtain one.**

Impact: a **monetized** Twitch stream (subs / bits / ads) is plausibly a
revenue-generating activity using the model's output -> XTTS v2 is **not safe**
for that use case. It is fine only for a pure non-monetized hobby stream.

## Commercially-safe alternatives (not yet spiked)

If the stream is or will be monetized, build on a permissively-licensed cloner:

| Engine | License | Notes |
|---|---|---|
| **Chatterbox / Chatterbox Turbo** (Resemble AI) | **MIT** | zero-shot clone from ~5s ref; Turbo ~6x real-time, ~75ms latency on GPU; built-in watermarking. Strongest commercial candidate. |
| **Zonos v0.1** (Zyphra) | **Apache 2.0** | zero-shot clone from 5-30s ref; 44kHz output; emotion/pitch conditioning. |

These have NOT been installed or benchmarked yet. Recommended next spike if the
license rules out XTTS.

## XTTS install gotchas (fresh 2026 env, Python 3.12)

Captured because the install is fragile:
- `coqui-tts` (Idiap fork) is the maintained package; original `TTS` is dead.
- `coqui-tts` does NOT pull `torch`/`torchaudio` -> install them explicitly.
- It declares `transformers>=4.57` but its tortoise layer imports
  `isin_mps_friendly`, which was **removed in transformers 5.x**. Pin
  `transformers>=4.57,<5` (4.57.6 works).
- torch >=2.9 requires `torchcodec` for audio IO -> `uv add torchcodec`
  (needs ffmpeg on PATH) or install `coqui-tts[codec]`.
- Set `COQUI_TOS_AGREED=1` for non-interactive model download (CPML prompt).

## Outcome

KokoClone selected (see DECISION at top). XTTS v2 rejected on license; quality
also favored KokoClone by ear. Chatterbox (MIT) / Zonos (Apache 2.0) are recorded
as viable commercial-safe alternatives if KokoClone disappoints on GPU latency,
but are not being pursued now.
