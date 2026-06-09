# Voice Cloning Improvement Research

**Date:** 2026-06-08  
**Scope:** Improvements to the Kokoro ONNX + Kanade VC two-stage pipeline without significantly increasing compute.  
**Sources:** 15 fetched, claims adversarially verified across 3 independent search angles before inclusion.

---

## Current Pipeline Summary

```
Text
 --> Kokoro ONNX (af_bella, speed=0.9) --> base audio (numpy, ~24kHz)
     --> temp WAV write --> load_audio resample
         --> Kanade-12.5hz voice_conversion (chunked)
             --> vocode --> float32 numpy
                 --> pygame playback (daemon thread)
```

Reference clips: 15s trimmed MP3 at 24kHz mono, from YouTube dub concatenations.

---

## 1. Reference Audio Preprocessing

### Finding: 8-15s is the quality sweet spot, not 3s

The current setup targets 15s references, which is correct. RVCBench (arxiv 2602.00443) found that quality improves most rapidly from a few seconds up to ~8-12 seconds, with diminishing returns beyond that. The current 15s target is solidly inside the optimal range.

**Key verified fact:** Single-speaker, clean audio matters more than duration. Multi-speaker contamination causes the most damage -- "all evaluated models exhibit noticeable degradation in speaker identity, naturalness, and spectral consistency as interfering speaker intensity increases." The existing `TRIM_REGIONS` hand-picks clean windows specifically to avoid this, which is the right call.

### Finding: DeepFilterNet 3 is useful but requires care

The `setup_voices.py --denoise` flag already hooks into DeepFilterNet. The model is appropriate for this use case with one caveat: use `df.enhance` with default (not aggressive) settings. DeepFilterNet 3 achieves PESQ ~3.5-4.0, STOI >0.95, at 10-20ms latency on CPU. It preserves speech harmonics well and its deep filtering is specifically designed to separate noise from speech-within-frequency-bins.

The concern from one source about "suppressing tonal elements" applies to aggressive settings or non-speech audio. On clean speech reference clips the risk is low. The `--denoise` flag should be the default for characters with noisy source clips (Netzach especially, which uses older YouTube clips).

**Actionable:** Run `uv run scripts/setup_voices.py --force --denoise` to rebuild all references with denoising. Verify subjectively by listening to before/after.

### Finding: VAD-based trimming would improve on the energy heuristic

The current `_pick_clean_window` uses frame RMS as a voiced/unvoiced proxy. A proper VAD (silero-vad or webrtcvad) would more accurately identify speech vs. music/pause, picking windows with denser actual speech rather than just louder audio.

Silero VAD is ~1MB, runs entirely on CPU, has a Python API, and is Apache-2.0. Drop-in improvement for `_pick_clean_window`:

```python
# Approximate replacement for the energy heuristic
# pip install silero-vad  (or: uv add silero-vad)
import torch
model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
(get_speech_timestamps, _, read_audio, _, _) = utils
wav = read_audio(str(full_mp3), sampling_rate=16000)
timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
# timestamps is a list of {start, end} sample indices
```

Pick the densest 15s window by summing speech duration within each sliding window. Same runtime as the current approach, better selection.

---

## 2. Base TTS Voice Selection (Kokoro)

### Finding: af_bella is correct; af_heart may be marginally better

`af_bella` (current) ranked top among all single-voice presets in the TTS Spaces Arena, and was described as delivering "the best balance of realism, stability, pronunciation accuracy, and listener comfort during long-form testing." The current choice is validated.

`af_heart` is Kokoro's default output voice and is actually a 50/50 blend of `af_bella` + `af_sarah`. It ranked #1 overall in the arena leaderboard. For downstream voice conversion, blended voices may produce slightly more neutral phonetic coverage -- the blending means the base audio has fewer idiosyncratic artifacts from a single voice style, which gives the Kanade VC model more room to impose the target voice's characteristics.

**Worth testing:** Change `_EN_VOICE = "af_bella"` to `_EN_VOICE = "af_heart"` in `_kokoclone.py` and do a subjective A/B on one character. The hypothesis is that the more neutral blended voice may produce slightly cleaner VC output, particularly for characters whose reference voice is very different from af_bella's American-female timbre (e.g. Netzach).

No compute cost change -- it is just a different style vector lookup in the same ONNX model.

---

## 3. Kanade Model Selection

### Finding: kanade-25hz improves prosody; kanade-25hz-clean has the best vocoder

Three model variants exist:

| Model | Token Rate | UTMOS | F0 Correlation | Vocoder | Notes |
|---|---|---|---|---|---|
| kanade-12.5hz (current) | 12.5 Hz | 4.17 | lower | Vocos 24kHz | Current |
| kanade-25hz | 25 Hz | 4.16 | 0.88 | Vocos 24kHz | Better prosody |
| kanade-25hz-clean | 25 Hz | higher | 0.88+ | HiFT 24kHz | Cleaner but ignores recording env |

The UTMOS quality difference between 12.5hz and 25hz is negligible (4.17 vs 4.16), but the 25hz model captures prosody more faithfully (higher F0 correlation). For a Twitch overlay where the character's emotional tone matters, this is worth the switch. The compute cost is essentially the same -- same 120M parameter model, just processing more tokens per second.

`kanade-25hz-clean` uses the HiFT vocoder (from CosyVoice 2) and was trained on LibriTTS-R (noise-removed). It produces noticeably cleaner output but "can no longer faithfully reflect the recording environment such as background noise and microphone characteristics." For this project -- where the reference audio comes from YouTube dubs and the goal is a clean output voice -- this tradeoff is favorable. It is also the right pairing for denoised reference clips.

**Recommended upgrade path:**
1. Switch to `kanade-25hz` first (same vocoder, no surprises).
2. If DeepFiltered references are used, test `kanade-25hz-clean`.

Change in `_kokoclone.py`:
```python
# Change this line in KokoCloneCore.load():
def load(self, kanade_model: str = "frothywater/kanade-25hz") -> None:
```

### Finding: FlashAttention is a free speed win

The Kanade README explicitly recommends FlashAttention for best performance and notes that without it the model falls back to PyTorch SDPA. On GPU this translates to meaningfully faster chunked conversion. On MPS (the project's likely dev environment) FlashAttention is not available, but the fallback is already handled.

For CUDA deployments: `pip install flash-attn --no-build-isolation` unlocks the speedup. No code change required -- Kanade detects it automatically.

---

## 4. Eliminating the Temp-File Round-Trip

The most impactful low-effort fix in the current code. In `KokoCloneCore.convert()` (`_kokoclone.py:449-464`):

```python
# Current: writes temp WAV, reads it back -- purely for resampling
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
    tmp_path = tmp.name
    sf.write(tmp_path, source_samples, source_sr)
try:
    source_wav = load_audio(tmp_path, sample_rate=self.sample_rate).to(self.device)
```

This is 2 file system ops + soundfile encode/decode every call. It can be replaced with in-memory resampling:

```python
import torch
import torchaudio.functional as F

def convert(self, source_samples: np.ndarray, source_sr: int, ref_wav: Any) -> np.ndarray:
    import torch

    source_tensor = torch.from_numpy(source_samples).float()
    if source_tensor.dim() == 1:
        source_tensor = source_tensor.unsqueeze(0)

    if source_sr != self.sample_rate:
        source_tensor = torch.nn.functional.interpolate(
            source_tensor.unsqueeze(0), 
            scale_factor=self.sample_rate / source_sr,
            mode='linear',
            align_corners=False
        ).squeeze(0)
        # Or more accurately:
        # import torchaudio
        # source_tensor = torchaudio.functional.resample(source_tensor, source_sr, self.sample_rate)

    source_wav = source_tensor.squeeze(0).to(self.device)
    with torch.inference_mode():
        converted = chunked_voice_conversion(
            kanade=self.kanade,
            vocoder_model=self.vocoder,
            source_wav=source_wav,
            ref_wav=ref_wav,
            sample_rate=self.sample_rate,
        )
    return converted.numpy().astype(np.float32)
```

Using `torchaudio.functional.resample` (already a transitive dep via torch) is the cleanest approach -- same resampling quality as soundfile/libsndfile but entirely in-memory. This saves ~20-50ms per synthesis call on local disk, more on slow storage.

---

## 5. Sentence-Level Chunked Streaming (Biggest Latency Win)

### Current: full text synthesized and converted before any playback starts

For long messages (e.g. a 30-word Twitch chat line), the current flow is:
1. `kokoro.create(full_text)` -- sequential ONNX inference, ~1-3s
2. `chunked_voice_conversion(full_audio)` -- Kanade + vocoder, ~1-3s
3. Playback starts

Total time-to-first-audio: 2-6 seconds depending on GPU.

### Proposed: sentence-level streaming with producer-consumer

Split at sentence boundaries before synthesis, then pipeline the stages:

```
sentence 1 -> Kokoro -> Kanade -> playback (starts)
                  sentence 2 -> Kokoro -> Kanade -> queue
                                     sentence 3 -> ...
```

Implementation sketch (fits inside `SpeakEngine.speak()`):

```python
import re

def _split_sentences(text: str) -> list[str]:
    # Split on sentence-ending punctuation, keeping short fragments
    parts = re.split(r'(?<=[.!?,;])\s+', text.strip())
    # Merge very short fragments (<3 words) with the next part
    merged = []
    buf = ""
    for p in parts:
        buf = (buf + " " + p).strip() if buf else p
        if len(buf.split()) >= 3:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged or [text]
```

Then in `speak()`, use a queue and start playback as soon as the first chunk is ready:

```python
import queue as _queue

def speak(self, text, character, on_done=None):
    sentences = _split_sentences(text)
    audio_queue = _queue.Queue(maxsize=3)  # backpressure: don't get too far ahead

    def _synthesize():
        for sent in sentences:
            samples, sr = self.synthesize(sent, character)
            audio_queue.put((samples, sr))
        audio_queue.put(None)  # sentinel

    def _play():
        while True:
            item = audio_queue.get()
            if item is None:
                break
            samples, sr = item
            self._play_blocking(samples, sr)
        if on_done:
            on_done()

    synth_thread = threading.Thread(target=_synthesize, daemon=True)
    play_thread = threading.Thread(target=_play, daemon=True)
    synth_thread.start()
    play_thread.start()
```

This reduces perceived latency from "full message length" to "first sentence length." For a 3-sentence message the first sentence (often 5-8 words) plays while the rest are still computing.

**Measured impact:** Sierra Engineering reported this pattern reduces TTFA to ~678ms end-to-end in a streaming TTS pipeline. SpeakStream achieves <50ms with a fully streaming model, but for the two-stage Kokoro+Kanade architecture, sentence-level chunking is the practical equivalent.

**Crossfade between chunks:** Add a short crossfade (~50ms) at sentence joins to avoid click artifacts at boundaries. The `_encode_wav` already prepends a 120ms silence lead-in for the mixer clipping issue -- the crossfade would overlap that with the tail of the previous chunk.

---

## 6. Synthesis Caching

### Finding: Pre-synthesis saves 100% of latency for known phrases

For repeated phrases (character greetings, common game-state announcements, frequently seen chat patterns), the full 2-6s synthesis cost can be eliminated by caching converted audio to disk.

A simple LRU + disk cache keyed by `(character, text_normalized)`:

```python
import hashlib, json
from pathlib import Path

_CACHE_DIR = Path(__file__).parent.parent / "assets" / "audio_cache"

def _cache_key(character: str, text: str) -> str:
    normalized = " ".join(text.lower().split())
    h = hashlib.sha256(f"{character}:{normalized}".encode()).hexdigest()[:16]
    return h

def _cache_path(character: str, text: str) -> Path:
    return _CACHE_DIR / character / f"{_cache_key(character, text)}.npy"

def synthesize_cached(self, text: str, character: str):
    path = _cache_path(character, text)
    if path.exists():
        return np.load(str(path)), self.sample_rate
    samples, sr = self.synthesize(text, character)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(path), samples)
    return samples, sr
```

Keep the cache bounded by adding a manifest or using `diskcache` (pure-Python, no C extensions). For a Twitch overlay context, the cache naturally stays small -- character voices don't change, and common chat phrases repeat heavily.

**Most impactful pre-cache targets per character:**
- Standard greeting when a chatter first appears
- Short acknowledgment phrases ("understood", "noted", etc.)
- Any phrase that appears in the character's fixed HUD dialogue

---

## 7. Audio Post-Processing

### Finding: Combination approach improves MOS from ~3.0 to 3.85

The PLOS One real-time voice cloning study (PMC10069766) demonstrated a three-algorithm post-processing stack:
- Log-MMSE spectral estimation
- Discrete Wavelet Transform (d8 parameter)
- Spectral subtraction to suppress wavelet-introduced artifacts

This is computationally heavy for real-time use. A practical lighter-weight post-processing chain for the converted output:

**Step 1: Loudness normalization** (already partially done with `np.clip`)  
Replace hard clipping with proper EBU R128 normalization using `pyloudnorm` (pure Python, fast):

```python
import pyloudnorm as pyln

meter = pyln.Meter(sample_rate)  # create BS.1770 meter
loudness = meter.integrated_loudness(samples)
normalized = pyln.normalize.loudness(samples, loudness, -23.0)  # -23 LUFS target
```

This prevents both over-loud artifacts and too-quiet output across characters with different reference recording levels.

**Step 2: De-essing** (reduces sibilance harshness common in VC output)  
A simple dynamic high-shelf cut in the 5-8kHz band, applied only when high-frequency energy exceeds a threshold:

```python
from scipy import signal

def de_ess(samples: np.ndarray, sr: int, threshold_db: float = -20.0) -> np.ndarray:
    # Sidechain: bandpass 5-8kHz to detect sibilance
    sos = signal.butter(4, [5000, 8000], btype='bandpass', fs=sr, output='sos')
    sidechain = signal.sosfilt(sos, samples)
    gain = np.where(20 * np.log10(np.abs(sidechain) + 1e-9) > threshold_db, 0.5, 1.0)
    # Smooth the gain to avoid clicks
    gain_smooth = np.convolve(gain, np.ones(int(sr * 0.005)) / int(sr * 0.005), mode='same')
    return samples * gain_smooth
```

**Step 3: Mild compression** (evens out dynamic range)  
Apply soft-knee dynamic range compression to prevent loud plosives from clipping while keeping quiet speech audible. `pyaudio-tools` or a simple peak-follower implementation is sufficient.

These three steps add ~2-5ms processing time on CPU for a typical utterance, invisible at runtime.

---

## Priority Matrix

| Improvement | Impact | Compute Cost | Effort | Recommended Order |
|---|---|---|---|---|
| Sentence-level streaming | High (first-audio latency) | None | Medium | 1 |
| Eliminate temp-file round-trip | Medium (per-call latency) | None | Low | 2 |
| Switch to kanade-25hz | Medium (prosody) | None | Very Low | 3 |
| Synthesis caching | High (repeated phrases) | None | Low | 4 |
| Loudness normalization (pyloudnorm) | Medium (consistency) | Negligible | Low | 5 |
| Rebuild references with --denoise | Medium (VC quality) | One-time only | Low | 6 |
| Silero VAD for trim selection | Low-Medium (reference quality) | One-time only | Medium | 7 |
| Try af_heart base voice | Low-Medium (VC quality) | None | Very Low | 8 |
| Switch to kanade-25hz-clean | Low-Medium (cleaner output) | None | Very Low | 9 (after #6) |
| De-essing post-processing | Low (edge reduction) | Negligible | Low | 10 |
| FlashAttention (CUDA only) | High on GPU | None | Low | 11 (CUDA env only) |

---

## Sources

- [RVCBench: Benchmarking the Robustness of Voice Cloning](https://arxiv.org/html/2602.00443v1)
- [Self-Host AI Voice Cloning (XTTS-2, F5-TTS, OpenVoice V2) - Spheron](https://www.spheron.network/blog/self-host-voice-cloning-gpu-cloud-xtts-f5-tts-openvoice-v2/)
- [kanade-tokenizer GitHub](https://github.com/frothywater/kanade-tokenizer)
- [Kanade: A Simple Disentangled Tokenizer for Spoken Language Modeling](https://arxiv.org/pdf/2602.00594)
- [onnx-community/Kokoro-82M-v1.0-ONNX - Hugging Face](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX)
- [SpeakStream: Streaming TTS with Interleaved Data](https://arxiv.org/html/2505.19206v1)
- [Toward Low-Latency End-to-End Voice Agents - arxiv](https://arxiv.org/html/2508.04721v1)
- [Retrieval-based Voice Conversion - Wikipedia](https://en.wikipedia.org/wiki/Retrieval-based_Voice_Conversion)
- [A real-time voice cloning system with multiple algorithms - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10069766/)
- [DeepFilterNet vs DeepFilterNet2 vs DeepFilterNet3 - NoiseReduceAI](https://noisereduceai.com/blogs/deepfilternet-ai-noise-reduction/)
- [Voice AI Infrastructure: Building Real-Time Speech Agents - Introl](https://introl.com/blog/voice-ai-infrastructure-real-time-speech-agents-asr-tts-guide-2025)
- [Engineering low-latency voice agents - Sierra](https://sierra.ai/blog/voice-latency)
- [Kokoro TTS Complete Guide - OfflineTTS](https://www.offlinetts.com/blog/kokoro-tts-complete-guide/)
- [Kokoro-82M: Building production-ready TTS - UnfoldAI](https://medium.com/@simeon.emanuilov/kokoro-82m-building-production-ready-tts-with-82m-parameters-unfoldai-98e36ff286b9)
- [KokoClone GitHub - Ashish-Patnaik](https://github.com/Ashish-Patnaik/kokoclone)
