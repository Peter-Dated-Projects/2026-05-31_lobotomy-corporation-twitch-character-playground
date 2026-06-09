"""Character roster for the Sephirah renderer.

Each character is shown full-screen as a single pre-made 256x256 portrait
(under settings.SEPHIRAH_PORTRAITS_DIR). There is no sprite compositing: the
portrait is displayed as-is and gently bobs while the character is speaking.

The keys here are the canonical character ids; a voice/character name is matched
case-insensitively against them by the renderer.
"""

from __future__ import annotations

# Character id -> portrait filename (resolved against settings.SEPHIRAH_PORTRAITS_DIR).
SEPHIRAH_PORTRAITS: dict[str, str] = {
    "angela": "angela.png",
    "hod": "hod.png",
    "malkuth": "malkuth.png",
    "netzach": "netzach.png",
    "yesod": "yesod.png",
}
