"""SpeakEngine: turn a (filtered) chat message into spoken audio in a
character's cloned voice, using the vendored KokoClone core.

Public surface is intentionally small:

- :class:`SpeakEngine` -- load models once, ``synthesize`` (pure compute) and
  ``speak`` (synth + non-blocking playback).
- :attr:`SpeakEngine.is_speaking` -- True while audio is playing.
- :class:`SpeakEngineError` and its subclasses -- typed failures the caller can
  catch to skip an utterance instead of crashing the sim loop.

Config is taken from constructor args (the repo convention is that ``settings.py``
is owned by another track, so this module does not read or edit it).
"""

from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# Default roster of characters with a cloned reference voice (see
# scripts/setup_voices.py, which builds the reference WAV library).
DEFAULT_ROSTER = ("angela", "hod", "malkuth", "netzach", "yesod")

# Reference clips live alongside the package assets: assets/voices/<name>.<ext>.
_DEFAULT_VOICES_DIR = Path(__file__).resolve().parent.parent / "assets" / "voices"

# Accepted reference-clip container formats, in preference order. The reference
# library is built as MP3 by setup_voices.py; WAV/FLAC are also accepted so
# existing lossless clips keep working without a rebuild.
_REFERENCE_EXTS = (".mp3", ".wav", ".flac", ".ogg")


def _resolve_reference(voices_dir: Path, name: str) -> Path | None:
    """Return the reference clip for *name* under *voices_dir*, or None.

    Tries each extension in :data:`_REFERENCE_EXTS` order so a lossless clip
    wins over a lossy one when both exist.
    """
    for ext in _REFERENCE_EXTS:
        candidate = voices_dir / f"{name}{ext}"
        if candidate.is_file():
            return candidate
    return None


class SpeakEngineError(Exception):
    """Base class for all speak-engine failures the caller may catch."""


class SpeakUnavailableError(SpeakEngineError):
    """The ML stack (torch / kanade / kokoro) or its models could not be loaded.

    Wiring should catch this once at startup and disable the speak feature
    rather than letting it crash the render/sim loop.
    """


class MissingReferenceError(SpeakEngineError):
    """A character's reference voice clip is missing or unreadable."""


class SpeakEngine:
    """Synthesise and play character speech via KokoClone (Kokoro + Kanade VC).

    Heavy models load once at construction (~25-30s). Each roster character's
    reference-audio tensor is cached at startup so it is never re-read per call.
    """

    def __init__(
        self,
        voices_dir: str | Path | None = None,
        roster: tuple[str, ...] | list[str] = DEFAULT_ROSTER,
    ) -> None:
        self.voices_dir = Path(voices_dir) if voices_dir is not None else _DEFAULT_VOICES_DIR
        self.roster = tuple(roster)

        self._is_speaking = False  # True across synth + playback (the whole speak())
        self._is_playing = False   # True only while audio is actually on the mixer
        self._lock = threading.Lock()
        self._channel = None  # lazily reserved pygame mixer channel
        self._volume = 1.0  # playback gain in [0, 1]; applied to the channel

        # Load the ML core. Import failures -> typed unavailability error.
        try:
            from ._kokoclone import KokoCloneCore
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise SpeakUnavailableError(
                "KokoClone dependencies are not importable"
            ) from exc

        self._core = KokoCloneCore()
        try:
            self._core.load()
        except ImportError as exc:  # pragma: no cover - optional ML stack missing
            raise SpeakUnavailableError(
                "torch / kanade / kokoro stack is not installed"
            ) from exc
        except SpeakUnavailableError:
            # Already a clear, typed failure (e.g. the GPU-required message from
            # device selection) -- propagate as-is, do not re-wrap.
            raise
        except Exception as exc:  # model download / init failure
            raise SpeakUnavailableError(f"failed to load speak models: {exc}") from exc

        # Pre-cache one reference tensor per character.
        self._references: dict[str, object] = {}
        for name in self.roster:
            ref = _resolve_reference(self.voices_dir, name)
            if ref is None:
                exts = "|".join(e.lstrip(".") for e in _REFERENCE_EXTS)
                raise MissingReferenceError(
                    f"reference voice not found: {self.voices_dir / name}.({exts})"
                )
            try:
                self._references[name] = self._core.load_reference(ref)
            except Exception as exc:
                raise MissingReferenceError(
                    f"failed to load reference voice {ref}: {exc}"
                ) from exc

    @property
    def sample_rate(self) -> int:
        """Output sample rate of synthesised/converted audio."""
        return self._core.sample_rate

    @property
    def is_speaking(self) -> bool:
        """True for the whole ``speak`` call -- synthesis AND playback.

        Note this is True during the (multi-second) synthesis phase before any
        audio is audible. For "is sound actually coming out right now", use
        :attr:`is_playing`.
        """
        with self._lock:
            return self._is_speaking

    @property
    def is_playing(self) -> bool:
        """True only while synthesized audio is actually playing on the mixer.

        Unlike :attr:`is_speaking`, this stays False during synthesis and flips
        True the moment the clip starts on the channel. Use it to drive visuals
        that should track audible speech (e.g. a talking bob)."""
        with self._lock:
            return self._is_playing

    @property
    def volume(self) -> float:
        """Current playback gain in [0.0, 1.0]."""
        with self._lock:
            return self._volume

    def set_volume(self, volume: float) -> None:
        """Set playback gain, clamped to [0.0, 1.0].

        Applies to the live channel immediately (so a drag mid-utterance is
        audible) and is re-applied to every future utterance in
        :meth:`_play_blocking`. Thread-safe: callable from a UI/main thread
        while playback runs on the worker thread.
        """
        vol = max(0.0, min(1.0, float(volume)))
        with self._lock:
            self._volume = vol
            channel = self._channel
        if channel is not None:
            channel.set_volume(vol)

    def synthesize(self, text: str, character: str) -> tuple[np.ndarray, int]:
        """Synthesise *text* in *character*'s voice. Pure compute, no playback.

        Returns ``(samples, sample_rate)`` where samples is float32 mono.
        Raises :class:`MissingReferenceError` for an unknown character.
        """
        ref = self._references.get(character)
        if ref is None:
            raise MissingReferenceError(
                f"no reference voice loaded for character {character!r}"
            )
        base_samples, base_sr = self._core.synth_base(text)
        converted = self._core.convert(base_samples, base_sr, ref)
        return converted, self.sample_rate

    def speak(
        self,
        text: str,
        character: str,
        on_done: Optional[Callable[[], None]] = None,
    ) -> threading.Thread:
        """Synthesise *text* and play it back without blocking the caller.

        Synthesis (seconds) and playback both run on a daemon thread so the sim
        loop is never stalled. ``is_speaking`` is True from the moment this is
        called until playback ends, at which point *on_done* (if given) fires.

        Returns the worker thread (useful for tests that want to join it).
        Raises :class:`MissingReferenceError` synchronously for an unknown
        character so the caller can skip it cheaply.
        """
        if character not in self._references:
            raise MissingReferenceError(
                f"no reference voice loaded for character {character!r}"
            )

        with self._lock:
            self._is_speaking = True

        def _run() -> None:
            try:
                samples, sr = self.synthesize(text, character)
                self._play_blocking(samples, sr)
            finally:
                with self._lock:
                    self._is_speaking = False
                    self._is_playing = False  # safety net if synth/playback raised
                if on_done is not None:
                    on_done()

        thread = threading.Thread(target=_run, name=f"speak-{character}", daemon=True)
        thread.start()
        return thread

    # -- playback ----------------------------------------------------------

    def _play_blocking(self, samples: np.ndarray, sample_rate: int) -> None:
        """Play *samples* on a dedicated pygame mixer channel and block until
        playback finishes. Runs on the worker thread, never the sim loop."""
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=sample_rate)

        if self._channel is None:
            # Reserve a dedicated channel so speech never steals game SFX slots.
            count = pygame.mixer.get_num_channels()
            pygame.mixer.set_num_channels(count + 1)
            self._channel = pygame.mixer.Channel(count)

        # Load via a WAV file object (not buffer=): SDL_mixer parses the header
        # and resamples to the mixer's actual output format. buffer= would treat
        # the bytes as raw PCM already in the mixer's format -- when the mixer was
        # pre-initialized elsewhere (e.g. pygame.init() in the robot renderer opens
        # it at 44.1kHz stereo) our ~24kHz mono samples would play ~1.8x too fast.
        sound = pygame.mixer.Sound(file=io.BytesIO(self._encode_wav(samples, sample_rate)))
        with self._lock:
            self._channel.set_volume(self._volume)
        self._channel.play(sound)
        with self._lock:
            self._is_playing = True
        try:
            while self._channel.get_busy():
                pygame.time.wait(50)
        finally:
            with self._lock:
                self._is_playing = False

    # A short silence lead-in prepended to every clip before playback. The mixer
    # consistently swallows the first few ms of a clip -- SDL_mixer resamples our
    # ~24kHz mono audio up to its 44.1kHz stereo output and the hard onset at the
    # WAV boundary loses its leading edge, and on a freshly-init'd device the first
    # buffer is eaten entirely. Padding with silence means what gets clipped is the
    # pad, never speech. ~120ms is inaudible as latency but covers both effects.
    _LEAD_IN_SECONDS = 0.12

    @classmethod
    def _encode_wav(cls, samples: np.ndarray, sample_rate: int) -> bytes:
        """Encode float32 mono samples to an in-memory 16-bit PCM WAV.

        Going through a WAV buffer (rather than pygame.sndarray) avoids having
        to match the mixer's exact array format and is robust across mixer init.
        A silence lead-in is prepended so the mixer's start-of-clip clipping eats
        the pad instead of the first word (see :attr:`_LEAD_IN_SECONDS`).
        """
        import soundfile as sf

        clipped = np.clip(samples, -1.0, 1.0)
        pad = np.zeros(int(cls._LEAD_IN_SECONDS * sample_rate), dtype=clipped.dtype)
        padded = np.concatenate([pad, clipped])
        buf = io.BytesIO()
        sf.write(buf, padded, sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()
