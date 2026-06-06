# Voice Cloning Research: Sephirah TTS

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

## Deployment options

**Option 1 (default): run Kokoro directly on the streaming PC.**
5070Ti handles the 82M model trivially. Start here.

**Option 2 (fallback): host Kokoro as a local HTTP endpoint on a separate machine (Mac or second PC).**
FastAPI server, streaming PC calls `http://192.168.x.x:8000/speak` with the message, gets back audio. ~1-5ms LAN round-trip overhead. Use this only if GPU contention is observed in practice — unlikely.

XTTS v2 is set aside: larger model, slower, unnecessary given the hardware.

```
uv add kokoro soundfile torch
brew install espeak-ng   # macOS; apt-get install espeak-ng on Linux
```

KokoClone (community extension) adds zero-shot voice cloning via ECAPA-TDNN speaker encoder: provide reference WAV clips, extract a voice embedding (192-float numpy array), save as `<character>_profile.npy`. At runtime, load the profile and pass to the synthesis call. No gradient updates, no GPU.

```python
from kokoro import KPipeline

pipeline = KPipeline(lang_code='en-us')  # load once at startup
# per speak event:
audio = pipeline(filtered_message, voice=speaker_embedding)
```

Multiple reference clips per character = better profile. Extract 5-10 clean lines from the YouTube video, run the encoder over all of them, average the embeddings.

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
