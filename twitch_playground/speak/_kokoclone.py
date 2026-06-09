"""Vendored, trimmed KokoClone voice-clone core.

Adapted from KokoClone (https://github.com/Ashish-Patnaik/kokoclone),
files ``core/cloner.py`` and ``core/chunked_convert.py``. Original project
license: Apache-2.0. This copy keeps only the English synth + voice-conversion
path this project needs and routes model downloads through the Hugging Face
cache instead of the working directory.

The pipeline is two stages:

1. Kokoro (ONNX) synthesises the text in a fixed preset English voice.
2. The Kanade voice-conversion model re-voices that audio toward a reference
   waveform (the target character's cloned voice), then a vocoder renders it.

All heavy third-party imports (torch, kanade_tokenizer, kokoro_onnx, misaki,
soundfile, huggingface_hub) happen inside :meth:`KokoCloneCore.load` so that
importing this module never requires the ML stack to be installed.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import types
from pathlib import Path
from typing import Any, Callable

import numpy as np

# SpeakUnavailableError is defined in tts.py. tts imports KokoCloneCore lazily
# (inside SpeakEngine.__init__), so importing the error here at module scope does
# NOT create a cycle: whichever module loads first, the other's top level does
# not import back into it.
from .tts import SpeakUnavailableError

# espeak-ng truncates its data path at an internal fixed buffer (~160 chars).
# When the bundled espeak-ng-data sits under a deep venv path it silently falls
# back to a non-existent compiled-in default and English phonemization fails.
# Keep our short symlink/copy well under that.
_ESPEAK_PATH_LIMIT = 150


def _short_espeak_data_path() -> str | None:
    """Return a short path to espeak-ng's data, copying it out of a too-long
    bundled location if needed. Returns None if espeakng_loader is unavailable.

    The returned path is meant to be passed to ``kokoro_onnx.EspeakConfig`` so
    Kokoro's Tokenizer uses it (Kokoro otherwise resets the data path to the
    long bundled location when it builds its Tokenizer)."""
    try:
        import espeakng_loader
    except ImportError:
        return None

    bundled = espeakng_loader.get_data_path()
    if len(bundled) < _ESPEAK_PATH_LIMIT:
        return bundled

    # Use a real copied directory, NOT a symlink: espeak resolves the data path
    # to its real location, so a symlink would expand back to the long bundled
    # path and truncate again. A one-time copy into the temp dir stays short.
    short = os.path.join(tempfile.gettempdir(), "kokoclone-espeak-data")
    if not os.path.isfile(os.path.join(short, "phontab")):
        if os.path.islink(short) or os.path.isfile(short):
            os.unlink(short)
        elif os.path.isdir(short):
            shutil.rmtree(short)
        shutil.copytree(bundled, short)
    return short

# Hugging Face repo holding the Kokoro ONNX model + voices pack used by KokoClone.
_HF_REPO = "PatnaikAshish/kokoclone"
_KOKORO_MODEL = "model/kokoro.onnx"
_KOKORO_VOICES = "voice/voices-v1.0.bin"

# Fixed English preset voice the base TTS speaks in before voice conversion.
_EN_VOICE = "af_bella"
_EN_SPEED = 0.9


# ---------------------------------------------------------------------------
# Device selection
# ---------------------------------------------------------------------------
#
# The speak pipeline runs faster than real-time only on a GPU. Plain `torch`
# from PyPI installs a CPU-only wheel on Windows/Linux, so it is easy to end up
# on CPU (RTF ~1.4, slower than real-time) without noticing. These helpers make
# the device choice explicit, loud in stdout, and configurable via env:
#
#   SPEAK_DEVICE      cuda | mps | cpu | auto   (default auto = CUDA -> MPS -> CPU)
#   SPEAK_REQUIRE_GPU truthy -> raise if no usable GPU instead of using CPU
#
# torch is passed in (not imported here) so this stays import-free and unit-
# testable with a stub.

_TRUTHY = frozenset({"1", "true", "yes", "on", "y", "t"})


def _env_bool(value: str | None, *, default: bool = False) -> bool:
    """Parse a boolean-ish env value (1/true/yes/on). Empty/None -> *default*."""
    if value is None:
        return default
    value = value.strip().lower()
    if value == "":
        return default
    return value in _TRUTHY


def _resolve_device(
    torch: Any,
    *,
    require_gpu: bool,
    override: str | None,
    log: Callable[[str], None] = print,
) -> Any:
    """Pick the compute device, preferring CUDA -> MPS -> CPU.

    *override* (SPEAK_DEVICE) forces a specific backend: ``cuda``/``mps``/``cpu``,
    or ``auto`` (default) for the preference order. Always logs the chosen device.

    Raises :class:`SpeakUnavailableError` when the resolved device is CPU and
    *require_gpu* is set, or when an explicit cuda/mps override is unavailable.
    On CPU (allowed) it logs a prominent slow-path warning. Returns a
    ``torch.device``. Note: MPS being *available* here does not guarantee the
    models load on it -- :meth:`KokoCloneCore.load` wraps the MPS load and falls
    back to CPU if it errors.
    """
    override = (override or "auto").strip().lower()
    if override not in ("auto", "cuda", "mps", "cpu"):
        log(f"[speak] WARNING: unknown SPEAK_DEVICE={override!r}; falling back to auto")
        override = "auto"

    cuda_ok = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, "mps", None)
    mps_ok = bool(mps_backend is not None and mps_backend.is_available())

    if override == "cuda":
        if not cuda_ok:
            raise SpeakUnavailableError(
                "SPEAK_DEVICE=cuda but CUDA is not available on this machine"
            )
        chosen = "cuda"
    elif override == "mps":
        if not mps_ok:
            raise SpeakUnavailableError(
                "SPEAK_DEVICE=mps but MPS is not available on this machine"
            )
        chosen = "mps"
    elif override == "cpu":
        chosen = "cpu"
    elif cuda_ok:
        chosen = "cuda"
    elif mps_ok:
        chosen = "mps"
    else:
        chosen = "cpu"

    if chosen == "cpu":
        if require_gpu:
            raise SpeakUnavailableError(
                "GPU required but none available; set SPEAK_REQUIRE_GPU=0 to allow CPU"
            )
        log(
            "[speak] WARNING: no GPU -- running speak on CPU, which is SLOWER than "
            "real-time (RTF ~1.4). Set SPEAK_REQUIRE_GPU=1 to fail loud instead."
        )

    log(f"[speak] device={chosen}")
    return torch.device(chosen)


# ---------------------------------------------------------------------------
# Chunked voice conversion (vendored verbatim from core/chunked_convert.py)
# ---------------------------------------------------------------------------
#
# On CUDA the source waveform is split into overlapping chunks so peak
# activation memory stays within a VRAM budget. On CPU the waveform is still
# chunked to respect the Kanade mel_decoder RoPE sequence-length ceiling
# (precomputed for 1024 mel frames; mel frames = samples // hop_length + 1,
# hop_length = 256, so a window of ~10.9s is the hard ceiling). A safety margin
# and a 0.5s context overlap on each side keep chunks comfortably under that.

_SECONDS_PER_GB = 10.0
_OVERLAP_SECONDS = 0.5
_ROPE_MAX_FRAMES = 1024
_MEL_HOP_LENGTH = 256
_ROPE_SAFETY_MARGIN = 0.75


def chunked_voice_conversion(
    kanade: Any,
    vocoder_model: Any,
    source_wav: Any,
    ref_wav: Any,
    sample_rate: int,
    vram_fraction: float = 0.9,
) -> Any:
    """Convert *source_wav* toward *ref_wav*'s voice in VRAM/RoPE-safe chunks.

    Returns a 1-D CPU float32 ``torch.Tensor`` (the converted waveform).
    """
    import torch
    from kanade_tokenizer import vocode

    device = source_wav.device
    n_samples = source_wav.shape[-1]

    overlap_samples = int(_OVERLAP_SECONDS * sample_rate)
    rope_max_window = (_ROPE_MAX_FRAMES - 1) * _MEL_HOP_LENGTH
    rope_safe_chunk = int((rope_max_window - 2 * overlap_samples) * _ROPE_SAFETY_MARGIN)

    if device.type == "cuda":
        total_vram_bytes = torch.cuda.get_device_properties(device).total_memory
        budget_gb = (total_vram_bytes * vram_fraction) / (1024 ** 3)
        vram_chunk_samples = int(max(5.0, budget_gb * _SECONDS_PER_GB) * sample_rate)
        chunk_samples = min(vram_chunk_samples, rope_safe_chunk)
    else:
        # CPU: no VRAM limit, but still respect the RoPE ceiling for quality.
        chunk_samples = rope_safe_chunk

    # Short-circuit when the whole clip fits in one chunk.
    if n_samples <= chunk_samples:
        with torch.inference_mode():
            mel = kanade.voice_conversion(
                source_waveform=source_wav, reference_waveform=ref_wav
            )
            wav = vocode(vocoder_model, mel.unsqueeze(0))
        return wav.squeeze().cpu()

    # Chunked processing with overlap context on each side.
    overlap_frames = overlap_samples // _MEL_HOP_LENGTH
    mel_parts: list[Any] = []
    pos = 0

    while pos < n_samples:
        win_start = max(0, pos - overlap_samples)
        win_end = min(n_samples, pos + chunk_samples + overlap_samples)
        chunk = source_wav[..., win_start:win_end]

        with torch.inference_mode():
            mel_chunk = kanade.voice_conversion(
                source_waveform=chunk, reference_waveform=ref_wav
            )

        # Free the GPU buffer before the next chunk.
        mel_chunk = mel_chunk.cpu()

        left_trim = 0 if pos == 0 else overlap_frames
        right_trim = (
            mel_chunk.shape[-1]
            if win_end >= n_samples
            else mel_chunk.shape[-1] - overlap_frames
        )
        mel_parts.append(mel_chunk[..., left_trim:right_trim])

        if device.type == "cuda":
            torch.cuda.empty_cache()

        # This chunk's window already reached the end, so it emitted [pos,
        # n_samples] in full (right_trim kept everything). Stop here -- stepping
        # pos += chunk_samples could land just short of n_samples and spawn one
        # more chunk that re-emits the tail, duplicating the last words.
        if win_end >= n_samples:
            break
        pos += chunk_samples

    full_mel = torch.cat(mel_parts, dim=-1).to(device)
    with torch.inference_mode():
        wav = vocode(vocoder_model, full_mel.unsqueeze(0))
    return wav.squeeze().cpu()


def _patch_kokoro_compat(kokoro: Any) -> Any:
    """Patch a kokoro_onnx instance for model exports with mixed input conventions.

    Vendored from core/cloner.py. Some Kokoro ONNX exports expect ``input_ids``
    plus a float ``speed`` tensor; the stock ``_create_audio`` does not match
    that signature, so we swap in a compatible implementation when detected.
    """
    import numpy as _np
    from kokoro_onnx.config import MAX_PHONEME_LENGTH, SAMPLE_RATE

    input_types = {meta.name: meta.type for meta in kokoro.sess.get_inputs()}
    if input_types.get("speed") != "tensor(float)" or "input_ids" not in input_types:
        return kokoro

    def _create_audio_compat(instance, phonemes, voice, speed):
        if len(phonemes) > MAX_PHONEME_LENGTH:
            phonemes = phonemes[:MAX_PHONEME_LENGTH]
        tokens = _np.array(instance.tokenizer.tokenize(phonemes), dtype=_np.int64)
        assert len(tokens) <= MAX_PHONEME_LENGTH
        voice_style = voice[len(tokens)]
        inputs = {
            "input_ids": [[0, *tokens, 0]],
            "style": _np.array(voice_style, dtype=_np.float32),
            "speed": _np.array([speed], dtype=_np.float32),
        }
        audio = instance.sess.run(None, inputs)[0]
        return audio, SAMPLE_RATE

    kokoro._create_audio = types.MethodType(_create_audio_compat, kokoro)
    return kokoro


def _patch_fsq_mps_compat() -> None:
    """Make Kanade's FSQ index reduction run on Apple's MPS backend.

    ``FSQ.codes_to_indices`` (kanade_tokenizer/module/fsq.py) computes codebook
    indices via a float64 basis product. MPS has no float64 dtype, so the op
    raises on Apple Silicon. We relocate ONLY that reduction to CPU -- the
    float64 math is preserved verbatim, so the resulting indices are
    bit-identical to upstream -- and move the long result back to the original
    device. The heavy Kanade model stays on MPS; only this tiny integer
    reduction hops to CPU. Idempotent: safe to call on every load.
    """
    import torch
    from kanade_tokenizer.module import fsq

    if getattr(fsq.FSQ, "_mps_float64_patched", False):
        return

    _orig = fsq.FSQ.codes_to_indices

    def codes_to_indices(self, zhat):  # mirrors upstream, CPU float64 on MPS
        if zhat.device.type != "mps":
            return _orig(self, zhat)
        out_device = zhat.device
        half_width = (self._levels // 2).to("cpu")
        scaled = (zhat.to("cpu") * half_width) + half_width
        indices = (scaled * self._basis.to("cpu").to(torch.float64)).to(torch.long).sum(dim=-1)
        return indices.to(out_device)

    fsq.FSQ.codes_to_indices = codes_to_indices
    fsq.FSQ._mps_float64_patched = True


class KokoCloneCore:
    """English-only KokoClone engine: Kokoro synth + Kanade voice conversion.

    Heavy models are loaded once in :meth:`load`. Call :meth:`synth_base` to
    produce base TTS audio, then :meth:`convert` to re-voice a source waveform
    toward a reference tensor.
    """

    def __init__(self) -> None:
        self.device: Any = None
        self.kanade: Any = None
        self.vocoder: Any = None
        self.kokoro: Any = None
        self.sample_rate: int = 0
        self._loaded = False

    def _load_kanade(self, kanade_model: str) -> None:
        """Load the Kanade voice-conversion model + vocoder onto ``self.device``.

        Split out from :meth:`load` so the MPS-failure path can retry it on CPU.
        """
        from kanade_tokenizer import KanadeModel, load_vocoder

        # MPS lacks float64; relocate FSQ's index reduction to CPU so the model
        # can run on Apple Silicon. No-op on CUDA/CPU. Idempotent.
        _patch_fsq_mps_compat()

        self.kanade = KanadeModel.from_pretrained(kanade_model).to(self.device).eval()
        self.vocoder = load_vocoder(self.kanade.config.vocoder_name).to(self.device)
        self.sample_rate = self.kanade.config.sample_rate

    def load(self, kanade_model: str = "frothywater/kanade-12.5hz") -> None:
        """Load Kanade + vocoder + Kokoro once.

        Device preference is CUDA -> MPS -> CPU, configurable via the
        ``SPEAK_DEVICE`` and ``SPEAK_REQUIRE_GPU`` env vars (see
        :func:`_resolve_device`). The selected device is logged at init.

        MPS is untested for Kanade/Kokoro and torch's MPS backend has gaps, so an
        MPS model-load failure falls back to CPU with a warning -- unless
        ``SPEAK_REQUIRE_GPU`` is set, in which case it raises.

        Raises ImportError if the ML stack is not installed (the caller turns that
        into a typed unavailability error) and :class:`SpeakUnavailableError` when
        a GPU is required but unavailable.
        """
        import torch
        from huggingface_hub import hf_hub_download
        from kokoro_onnx import EspeakConfig, Kokoro

        require_gpu = _env_bool(os.environ.get("SPEAK_REQUIRE_GPU"), default=False)
        override = os.environ.get("SPEAK_DEVICE")
        self.device = _resolve_device(torch, require_gpu=require_gpu, override=override)

        try:
            self._load_kanade(kanade_model)
        except Exception as exc:
            # MPS is best-effort: torch's MPS backend has op coverage gaps, so a
            # load failure there is expected to be recoverable on CPU.
            if self.device.type != "mps":
                raise
            if require_gpu:
                raise SpeakUnavailableError(
                    f"SPEAK_REQUIRE_GPU=1 and MPS model load failed: {exc}"
                ) from exc
            print(
                f"[speak] WARNING: MPS model load failed ({exc}); falling back to CPU"
            )
            self.device = torch.device("cpu")
            print("[speak] device=cpu")
            self._load_kanade(kanade_model)

        # Download into the HF cache (returns an absolute path); do NOT pollute
        # the working directory the way the upstream _ensure_file did.
        model_path = hf_hub_download(_HF_REPO, _KOKORO_MODEL)
        voices_path = hf_hub_download(_HF_REPO, _KOKORO_VOICES)

        # Give Kokoro's Tokenizer a short espeak data path; the bundled path can
        # exceed espeak-ng's internal path buffer when the venv is deeply nested.
        data_path = _short_espeak_data_path()
        espeak_config = EspeakConfig(data_path=data_path) if data_path else None
        kokoro = Kokoro(model_path, voices_path, espeak_config=espeak_config)
        self.kokoro = _patch_kokoro_compat(kokoro)
        self._loaded = True

    def load_reference(self, path: str | Path) -> Any:
        """Load a reference WAV as a tensor on the active device, resampled to
        the Kanade sample rate. Used to pre-cache per-character references."""
        from kanade_tokenizer import load_audio

        return load_audio(str(path), sample_rate=self.sample_rate).to(self.device)

    def synth_base(self, text: str) -> tuple[np.ndarray, int]:
        """Synthesise *text* in the fixed English preset voice (pre-conversion)."""
        samples, sr = self.kokoro.create(
            text, voice=_EN_VOICE, speed=_EN_SPEED, lang="en-us"
        )
        return samples, sr

    def convert(self, source_samples: np.ndarray, source_sr: int, ref_wav: Any) -> np.ndarray:
        """Re-voice base audio toward *ref_wav*. Returns float32 numpy samples
        at :attr:`sample_rate`.

        ``ref_wav`` is a pre-loaded reference tensor (see :meth:`load_reference`).
        """
        import soundfile as sf
        import torch
        from kanade_tokenizer import load_audio

        # Round-trip base audio through a temp WAV so load_audio resamples it to
        # the Kanade rate exactly as the verified spike did.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            sf.write(tmp_path, source_samples, source_sr)
        try:
            source_wav = load_audio(tmp_path, sample_rate=self.sample_rate).to(self.device)
            with torch.inference_mode():
                converted = chunked_voice_conversion(
                    kanade=self.kanade,
                    vocoder_model=self.vocoder,
                    source_wav=source_wav,
                    ref_wav=ref_wav,
                    sample_rate=self.sample_rate,
                )
            return converted.numpy().astype(np.float32)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
