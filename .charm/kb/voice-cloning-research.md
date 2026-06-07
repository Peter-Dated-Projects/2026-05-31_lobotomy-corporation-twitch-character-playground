# Voice Cloning Research: Sephirah TTS

> SUPERSEDED IN PART (2026-06-07): the engine details below predate the runtime
> spikes. See `tts-engine-decision.md` for the current call — KokoClone and
> XTTS v2 were both benchmarked and A/B'd; **KokoClone was chosen** (better
> quality by ear, and its whole stack is MIT/Apache = commercial-safe), XTTS v2
> rejected (non-commercial weights). This doc is kept for the model survey and
> the reference-audio / preprocessing pipeline, which are still valid.

## Key finding: no training needed

Zero-shot voice cloning synthesizes in a target voice from a short reference clip at runtime — no training loop, no gradient updates. All viable options below support this. Fine-tuning only adds value with 15-60+ minutes of clean audio, which we won't have from the YouTube dub clips.

---

## Model comparison (CPU-first)

| Model | CPU first-audio latency | Reference audio needed | Zero-shot | pip installable |
|---|---|---|---|---|
| **Kokoro + KokoClone** | ~150ms per 10s of output | 3-10s | Yes | Yes |
| **XTTS v2** | ~1500ms per sentence | 6s (min 3s) | Yes | Yes |
| **GPT-SoVITS** | RTF ~0.5 on M4 CPU | 5s | Yes | Via requirements.txt |
| F5-TTS | ~7m40s for 8 words on CPU | 3s | Yes | GPU-only in practice |
| RVC | Not real-time on CPU | 5-10 min (training required) | No | Yes |
| Bark | ~3000ms+ | N/A | No cloning | Yes |

F5-TTS and RVC are eliminated. F5-TTS is CPU-unusable. RVC requires actual training data and isn't real-time on CPU.

---

## Recommendation: Kokoro + KokoClone

Hardware: streaming PC has an RTX 5070Ti. Kokoro is an 82M parameter model — trivially small, ~1-2% GPU utilization during synthesis, invisible to game/OBS.

**Kokoro** is the only model that fits. ~150ms per 10 seconds of synthesized output means a typical 5-word chat message synthesizes in under 50ms on CPU. Apache 2.0, no GPU required, no training.

> NOTE (2026-06-07 spike): the ~150ms figure is for **bare Kokoro only**. The
> cloning feature needs the full KokoClone pipeline (Kokoro + Kanade VC), which
> measured **RTF ~1.4x on CPU** — slower than real-time. See "Spike status"
> below. CPU is not a viable deployment path; GPU latency is still unmeasured.

## Deployment options

**Option 1 (default): run Kokoro directly on the streaming PC.**
5070Ti handles the 82M model trivially. Start here.

**Option 2 (fallback): host Kokoro as a local HTTP endpoint on a separate machine (Mac or second PC).**
FastAPI server, streaming PC calls `http://192.168.x.x:8000/speak` with the message, gets back audio. ~1-5ms LAN round-trip overhead. Use this only if GPU contention is observed in practice — unlikely.

XTTS v2 is set aside: larger model, slower, unnecessary given the hardware.

```
uv add kokoro-onnx "misaki[en]" soundfile torch torchaudio huggingface_hub
uv add "git+https://github.com/frothywater/kanade-tokenizer"
brew install espeak-ng   # macOS; apt-get install espeak-ng on Linux
```

### How KokoClone actually works (verified by reading the source, 2026-06-07)

CORRECTION: an earlier version of this doc described KokoClone as adding zero-shot
cloning "via an ECAPA-TDNN speaker encoder" that produces a 192-float embedding
cached once at startup. **That is wrong.** Reading `core/cloner.py` in
`github.com/Ashish-Patnaik/kokoclone`, KokoClone is a **two-stage pipeline**:

1. **Kokoro-ONNX synthesizes the text in a fixed preset voice** (English uses
   `af_bella`). Kokoro itself does NOT clone — it has a fixed voice bank.
2. **The Kanade voice-conversion model re-voices that audio** to match the
   reference WAV (`frothywater/kanade-12.5hz` + a vocoder).

There is no precomputed speaker embedding. The reference WAV is loaded and the
Kanade VC pass runs on **every utterance** (chunked). The real cloning quality
and the runtime cost both come from the Kanade VC step, not from Kokoro.

Implication: this is RVC-style per-utterance voice conversion bolted onto a TTS
front-end, NOT lightweight embedding-conditioned synthesis. The per-speak cost is
`Kokoro synth + Kanade VC over the full output`. On the 5070Ti this is fine; the
CPU-fallback latency is the open question (see Spike status below).

Real API (`core/cloner.py`):

```python
from core.cloner import KokoClone

cloner = KokoClone()          # loads Kanade + vocoder once; auto-detects CUDA/CPU
# per speak event (reference WAV re-read each call unless we cache the loaded tensor):
cloner.generate(
    text=filtered_message,
    lang="en",
    reference_audio="assets/voices/<character>.wav",
    output_path="out.wav",
)
```

Multiple reference clips per character still helps the VC target. We concatenate
the dub clips per character in `scripts/setup_voices.py`, but a SHORT clean
segment (~10-15s) is a better VC reference than the full 8-11 min raw clip —
trim and denoise before using as the reference.

### Spike status (2026-06-07)

- [x] Architecture verified by source read (above) — KB corrected.
- [x] Reference audio downloaded for hod/malkuth/netzach/yesod via `scripts/setup_voices.py`.
- [x] Runtime test executed end-to-end (KokoClone + Kanade installed, ran on the
      hod reference clip). It works — produced intelligible cloned speech.

**Measured CPU latency (Apple Silicon Mac, `torch` CPU, no CUDA):**

| Phase | Time |
|---|---|
| `KokoClone()` init (load Kanade + vocoder + WavLM) | ~29s (one-time, at startup) |
| First `generate()` (downloads kokoro weights) | ~13s |
| **Steady-state `generate()`** | **~8.5s for 6.0s of audio = RTF ~1.4x** |

The Kanade voice-conversion pass dominates; this is NOT the "~150ms per 10s"
Kokoro-alone figure quoted earlier in this doc — that number describes bare
Kokoro and is misleading for the full KokoClone pipeline. **On CPU the pipeline
is slower than real-time (~1.4x), so the CPU-fallback deployment path is not
viable for a snappy speak feature.** A 5-10 word message would take ~5-10s on
CPU before audio starts. The RTX 5070Ti is expected to bring this well under
real-time, but that has NOT been measured yet (test ran on the Mac).

Sample artifacts for listening (gitignored):
`twitch_playground/assets/voices/_spike/hod_cloned_sample.wav` (cloned output)
vs `_spike/hod_reference.wav` (target). Judge likeness before committing the
roster to KokoClone.

**Recommendation after spike:** KokoClone is functional and the architecture is
sound, but two things must hold before adopting it: (1) GPU latency confirmed
acceptable on the actual streaming PC (CPU is a no-go), and (2) the cloned
output judged close enough to the target character. If GPU latency disappoints
or likeness is weak, XTTS v2 remains the fallback (also a per-utterance cost,
but a single-model zero-shot cloner rather than a TTS+VC chain).

---

## Reference audio requirements

- Zero-shot needs 3-10 seconds of clean reference audio
- Extract 30-60 second clean segments from each character's YouTube video
- More reference audio improves embedding quality with diminishing returns past ~30s (Kokoro) / ~10s (XTTS v2)
- Store as `assets/voices/<name>.wav` (gitignored, local only)

---

## Preprocessing pipeline

Dub videos have background music and SFX — must be removed before using as reference audio.

```bash
# 1. Download audio only
yt-dlp -x --audio-format wav --audio-quality 0 "<url>"

# 2. Trim to clean solo speech segment
ffmpeg -i input.wav -ss 00:00:05 -t 00:00:45 -ar 24000 -ac 1 -sample_fmt s16 trimmed.wav

# 3. Denoise (remove background music/SFX)
uv add deepfilternet
python -m df.enhance trimmed.wav -o cleaned.wav
```

`deepfilternet` runs on CPU in a few seconds per clip and is designed specifically to isolate speech from background score/SFX.

---

## Dubbed audio gotchas

- **Background scoring**: Nearly all dub videos have score/SFX underneath. deepfilternet handles this well.
- **Lip-sync pacing**: Dubbed speech is timed to match original lip movements, creating slightly unnatural pauses and rushed syllables. Pick the most naturally-paced lines when choosing which segment to clip. Multiple short segments can be concatenated if no single clean run is long enough.
- **Same-language advantage**: English reference -> English output gives significantly better prosody than Korean -> English (cross-lingual). Primary reason the SoundCloud Korean clips were dropped entirely.
- **Voice similarity ceiling**: Kokoro's zero-shot embedding is an approximation, not a perfect clone. For a Twitch overlay this is fine — viewers read the character name and robot body and fill in the rest.

---

## Setup script outline

`scripts/setup_voices.py` — run once per machine to build the reference WAV library:

```python
CHARACTERS = {
    "chesed":    {"url": "...", "start": "0:05", "duration": 40},
    "binah":     {"url": "...", "start": "0:08", "duration": 35},
    # ... populated when YouTube videos are identified
}
# yt-dlp download -> ffmpeg trim -> deepfilternet denoise -> save assets/voices/<name>.wav
```

---

## Runtime speak pipeline

```
speak event (channel point redemption)
  -> filter message (better-profanity, ~1ms)
  -> background thread:
       1. load assets/voices/<character>.wav  (cached at startup)
       2. kokoro pipeline(message, voice=embedding)  -> audio array (~50-150ms)
       3. pygame.mixer.Sound(audio) -> play on dedicated speak channel
       4. wait for playback to finish
       5. character.end_speak()
```

---

## Sources

- [Local TTS and Voice Cloning 2026 comparison](https://www.promptquorum.com/power-local-llm/local-tts-voice-cloning-piper-coqui-xtts)
- [12 Best Open-Source TTS Models Compared (2025)](https://www.inferless.com/learn/comparing-different-text-to-speech---tts--models-part-2)
- [Voice Cloning with Offline TTS: Kokoro, Kitten, and Piper](https://offlinetts.com/blog/voice-cloning-offline-tts-kokoro-kitten-piper/)
- [F5-TTS Fine Tuning Voice Cloning Guide](https://instavar.com/blog/ai-production-stack/F5_TTS_Fine_Tuning_Voice_Cloning_Guide)
- [RVC Voice Conversion Explained 2025](https://www.apatero.com/blog/rvc-retrieval-based-voice-conversion-explained-2025)
- [GPT-SoVITS GitHub](https://github.com/RVC-Boss/GPT-SoVITS)
- [Seed-VC GitHub](https://github.com/Plachtaa/seed-vc)
- [F5-TTS CPU inference issue thread](https://github.com/SWivid/F5-TTS/issues/403)
- [KokoClone GitHub](https://github.com/Ashish-Patnaik/kokoclone)
