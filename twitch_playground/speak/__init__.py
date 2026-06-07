"""Speak feature: clone-voice text-to-speech for character chat messages.

Manual smoke test (slow: first run downloads the Kokoro + Kanade model weights
from Hugging Face; CPU synthesis is roughly real-time, faster on CUDA). Not run
in CI. Requires the reference voice WAVs under ``assets/voices/<name>.wav``::

    from twitch_playground.speak import SpeakEngine
    eng = SpeakEngine()                       # loads models once (~25-30s cold)
    samples, sr = eng.synthesize("hello", "hod")
    print(samples.shape, sr)                  # -> (N,) float32, 24000

``eng.speak("hello", "hod")`` instead plays the audio on a background thread
without blocking the caller; poll ``eng.is_speaking`` or pass an ``on_done``
callback to know when playback ends.
"""

from .tts import (
    DEFAULT_ROSTER,
    MissingReferenceError,
    SpeakEngine,
    SpeakEngineError,
    SpeakUnavailableError,
)

__all__ = [
    "DEFAULT_ROSTER",
    "MissingReferenceError",
    "SpeakEngine",
    "SpeakEngineError",
    "SpeakUnavailableError",
]
