# Voice Quality Improvement Proposal

Four targeted changes to the Kokoro + Kanade pipeline, ranked by impact. Ordering updated after deep research: reference audio quality is the highest-leverage fix, not the model switch.

---

## Change 1: Fix the reference audio (highest impact)

**What:** Re-cut reference clips to speech-only segments with no background music, then denoise.

**Why it matters most:** The reference clip is what Kanade's WavLM encoder uses to extract speaker identity. WavLM encodes *everything* in the audio — speech and background alike — into the speaker embedding. When the reference has orchestral game score mixed in, Kanade encodes those instrument harmonics as part of the "voice", and tries to impose that contaminated identity on synthesized speech. For high-pitched characters this is especially damaging: the orchestral score's upper harmonics overlap directly with the most perceptually salient frequency bands of bright, high-pitched speech (2-8 kHz).

Verified: "A 3-second clip recorded in a quiet room will produce better embeddings than a 10-second clip with background music. The model has no mechanism to separate signal from noise at the embedding stage." (Spheron/fish.audio, corroborated across 4 sources)

Target SNR: at least 30 dB, 40 dB preferred (futurebeeai.com).

Current clips are 48kHz stereo YouTube-cut game dubs with background score throughout. Estimated SNR is 10-20 dB in most segments — well below threshold.

**Two-step fix:**

Step 1 — Re-cut to speech-only windows. Find segments where the character speaks without background music under them, or where the music is significantly quieter than speech. Even 8 seconds of clean speech beats 15 seconds of music-backed speech. Update `TRIM_REGIONS` in `setup_voices.py` with these hand-picked windows.

Step 2 — Apply DeepFilterNet denoising after cutting. Make `--denoise` the default instead of opt-in:

```python
# setup_voices.py, argparse section
# Before:
parser.add_argument("--denoise", action="store_true", help="run deepfilternet pass (needs deepfilternet)")
# After:
parser.add_argument("--no-denoise", action="store_true", help="skip deepfilternet denoising pass")

# And in build_character call:
# Before:
build_character(name, video_ids, force=args.force, denoise=args.denoise)
# After:
build_character(name, video_ids, force=args.force, denoise=not args.no_denoise)
```

For manually-cut clips (angela.mp3 and any others not in the CHARACTERS dict), run DeepFilterNet directly:
```bash
uv run python -m df.enhance twitch_playground/assets/voices/angela.mp3 -o twitch_playground/assets/voices/
```

**Reference clip quality checklist:**
- 8-15 seconds of continuous speech (RVCBench: quality plateaus at 8-12s)
- At least 60% of duration should be active speech — no long pauses or music breaks
- No overlapping speakers
- SNR at least 30 dB before denoising

**Risk:** Low-medium. Re-cutting requires listening. DeepFilterNet has an escape hatch (`--no-denoise`).

---

## Change 2: Switch Kanade model from `kanade-12.5hz` to `kanade-25hz`

**What:** Change the default model string in `KokoCloneCore.load()`.

**Why it helps — now with paper numbers:** From the Kanade paper (Table 2, voice conversion task):

| Model | F0 Pearson Correlation | UTMOS | Speaker Similarity |
|---|---|---|---|
| kanade-12.5hz | 0.640 | 4.167 | 77.6 |
| kanade-25hz | 0.707 | 4.156 | 77.1 |

The 25hz model has **10.5% better F0 tracking** at zero cost to perceptual quality (UTMOS within 0.01) and negligible cost to speaker identity. This directly explains the high-pitched voice problem: at 12.5 tokens/sec, the model encodes one semantic token per 80ms. A high-pitched voice at ~300 Hz has pitch periods of ~3.3ms — 24 full cycles per token. The model can't distinguish whether pitch rose and fell within that window, or stayed constant. At 25hz/40ms, temporal resolution doubles, and the F0 correlation improvement is directly measurable.

Same vocoder (Vocos 24kHz), same output sample rate, same chunking logic.

**Code change:**
```python
# _kokoclone.py, KokoCloneCore.load() signature
# Before:
def load(self, kanade_model: str = "frothywater/kanade-12.5hz") -> None:
# After:
def load(self, kanade_model: str = "frothywater/kanade-25hz") -> None:
```

**Risk:** Low. Same architecture, same vocoder. Model downloads via HuggingFace on first run.

---

## Change 3: Loudness normalization with `pyloudnorm`

**What:** Apply EBU R128 loudness normalization to the converted audio before playback.

**Why it helps:** The current `np.clip` in `_encode_wav` only prevents hard clipping — it does not equalize levels across characters. Each character's reference clip was recorded at a different level, so output volume varies significantly between characters. Normalizing to -23 LUFS (broadcast standard) makes every character consistently audible regardless of reference clip level.

`pyloudnorm` is pure Python, no native extensions, ~1ms per clip.

**Code change** (in `SpeakEngine.synthesize()`, after `convert()` returns):
```python
import pyloudnorm as pyln

def _normalize_loudness(samples: np.ndarray, sample_rate: int, target_lufs: float = -23.0) -> np.ndarray:
    meter = pyln.Meter(sample_rate)
    loudness = meter.integrated_loudness(samples)
    if loudness == float("-inf"):  # silence guard
        return samples
    return pyln.normalize.loudness(samples, loudness, target_lufs)
```

**Risk:** Very low. Deterministic linear operation. The silence guard handles the only edge case.

---

## Change 4: Try `af_heart` as the base TTS voice (low-confidence, worth testing)

**What:** Change the Kokoro preset from `af_bella` to `af_heart`.

**Why it might help:** The base TTS voice's F0 range determines how much pitch shift Kanade has to apply. Both af_bella and af_heart are mid-range American English female voices (~200Hz). For high-pitched characters like Hod (~280-340Hz), that's a ~80-140Hz pitch shift during voice conversion. The Pseudo-Cepstrum paper (arxiv 2512.16519) confirms that large F0 modifications in mel-based vocoders produce audible distortions because mel spectrograms conflate pitch with spectral character.

**Confidence caveat:** Deep research found no primary-source evidence that af_heart produces better VC output than af_bella for high-pitched targets. The "af_heart is a blend of af_bella + af_sarah" claim appears in some guides but is not confirmed in the Kokoro VOICES.md or model card. This change is a one-liner with no risk — worth testing and comparing subjectively — but do not expect it to be a significant fix.

**Code change:**
```python
# _kokoclone.py line 78
# Before:
_EN_VOICE = "af_bella"
# After:
_EN_VOICE = "af_heart"
```

**Risk:** Low. Same ONNX model, same inference path.

---

## Future: `kanade-25hz-clean` + HiFT vocoder

After denoised references are in place, consider testing `kanade-25hz-clean`. It uses the HiFT vocoder (from CosyVoice 2) instead of Vocos and was trained on LibriTTS-R (noise-removed). It produces cleaner output at the cost of no longer reflecting the recording environment — which is exactly what you want when the reference has been denoised. One-line change, same as the kanade-25hz swap.

Note: the Vocos 24kHz vocoder has a hard 12kHz Nyquist ceiling and its mel bins are coarser at high frequencies (logarithmic scaling means fewer bins per Hz above 6kHz). HiFT was specifically designed to address these limitations for high-frequency vocal synthesis.

---

## Combined Effect

Changes 1-3 address all three verified root causes:

- Clean reference audio (Change 1) removes music contamination from the WavLM speaker embedding — the single highest-leverage fix
- kanade-25hz (Change 2) increases F0 correlation by 10.5% directly measured from the paper — directly targets the high-pitch pitch-tracking problem
- pyloudnorm (Change 3) makes all characters consistently audible

None increase inference time. The only meaningful one-time cost is the reference rebuild.

---

## What This Does Not Fix

The two-stage pipeline (generic TTS to voice conversion) has a ceiling. Kanade VC can transfer timbre and basic prosody but cannot change underlying phoneme production or speaking style. Characters with very distinctive patterns (Hod's energetic rhythm, Angela's clipped precision) will always sound "close but wrong" at the prosody level. Moving that ceiling requires either fine-tuned character TTS or an end-to-end diffusion VC model — both are significantly more infrastructure.
