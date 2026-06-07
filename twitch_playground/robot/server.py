"""FastAPI backend for the robot TTS test harness.

Serves the control-panel UI and a small JSON API. The speak engine is heavy to
construct (loads ML models, ~25-30s) and may be unavailable (no torch / no
reference WAVs), so it is built once on a background thread at startup and the
server reports its status. When the engine is unavailable the API still runs in
"dry" mode: events are received and passed through the swear filter, just with
no audio -- enough to validate the event plumbing and filtering.

Endpoints:
  GET  /              -> the control-panel page
  GET  /api/health    -> engine status, device, roster, is_speaking
  GET  /api/roster    -> the list of robot voices
  POST /api/speak     -> {text, character?} -> filter + (if ready) speak
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from twitch_playground import settings
from twitch_playground.speak.filter import filter_message

_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Robot TTS test harness")


# --- engine lifecycle --------------------------------------------------------
# The engine is constructed on a background thread so the server comes up
# instantly and the UI can poll /api/health for readiness.


class _EngineState:
    def __init__(self) -> None:
        self.engine = None          # SpeakEngine | None
        self.status = "loading"     # loading | ready | unavailable
        self.detail = ""            # human-readable error when unavailable
        self.device = ""            # cuda | mps | cpu, once known
        # Who is speaking right now, for the optional renderer (frieren run robot)
        # to draw the face. (character, text) or None. The renderer clears it when
        # the engine stops speaking; harmless in headless robot-debug mode.
        self.active = None          # tuple[str, str] | None
        self._lock = threading.Lock()

    def is_speaking(self) -> bool:
        eng = self.engine
        return bool(eng and eng.is_speaking)


STATE = _EngineState()


def _load_engine() -> None:
    """Construct the SpeakEngine; record readiness or a typed failure reason."""
    try:
        from twitch_playground.speak import SpeakEngine

        engine = SpeakEngine(
            voices_dir=settings.SPEAK_VOICES_DIR,
            roster=settings.ROBOT_ROSTER,
        )
        # device lives on the engine's KokoClone core (a torch.device); surface
        # its type (cuda|mps|cpu) for the health panel.
        core = getattr(engine, "_core", None)
        dev = getattr(getattr(core, "device", None), "type", "") or ""
        with STATE._lock:
            STATE.engine = engine
            STATE.device = str(dev)
            STATE.status = "ready"
        print(f"[robot] speak engine ready (device={dev or 'unknown'})")
    except Exception as exc:  # SpeakUnavailableError / MissingReferenceError / etc.
        with STATE._lock:
            STATE.status = "unavailable"
            STATE.detail = f"{type(exc).__name__}: {exc}"
        print(
            "[robot] speak engine unavailable -- running in DRY mode "
            f"(filter only, no audio): {STATE.detail}"
        )


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_load_engine, name="engine-load", daemon=True).start()


# --- voice pairing -----------------------------------------------------------


def _pick_voice(username: str) -> str:
    """Deterministic md5(username) -> roster voice. Mirrors sim.world.pick_voice
    so a given username maps to the same Sephirah here as in the playground."""
    roster = settings.ROBOT_ROSTER
    digest = hashlib.md5((username or "anonymous").encode("utf-8")).hexdigest()
    return roster[int(digest, 16) % len(roster)]


# --- API ---------------------------------------------------------------------


class SpeakRequest(BaseModel):
    text: str
    character: str | None = None   # explicit voice, else paired from author
    author: str = "webui"          # mock username for deterministic pairing


@app.get("/api/health")
def health() -> dict:
    return {
        "status": STATE.status,
        "detail": STATE.detail,
        "device": STATE.device,
        "roster": settings.ROBOT_ROSTER,
        "is_speaking": STATE.is_speaking(),
    }


@app.get("/api/roster")
def roster() -> dict:
    return {"roster": settings.ROBOT_ROSTER}


@app.post("/api/speak")
def speak(req: SpeakRequest) -> dict:
    """Receive a mocked !say event: truncate, filter, pair a voice, and (when the
    engine is ready) speak it. Always returns the filtered text + chosen voice so
    the UI shows the result even in dry mode."""
    text = (req.text or "").strip()[: settings.SPEAK_MAX_MESSAGE_LEN]
    if not text:
        return {"ok": False, "error": "empty message"}

    filtered = filter_message(text)
    character = req.character or _pick_voice(req.author)
    if character not in settings.ROBOT_ROSTER:
        return {"ok": False, "error": f"unknown character {character!r}"}

    if STATE.status == "ready" and not STATE.is_speaking():
        try:
            STATE.engine.speak(filtered, character)
            STATE.active = (character, filtered)  # renderer picks this up to draw the face
            spoke = True
            note = "speaking"
        except Exception as exc:  # MissingReferenceError, etc.
            spoke = False
            note = f"engine error: {type(exc).__name__}: {exc}"
    elif STATE.status == "ready":
        spoke = False
        note = "busy (one utterance at a time)"
    else:
        spoke = False
        note = f"dry mode ({STATE.status}): filtered only, no audio"

    return {
        "ok": True,
        "spoke": spoke,
        "note": note,
        "character": character,
        "filtered": filtered,
        "censored": filtered != text,
        "engine_status": STATE.status,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


def main() -> None:
    """Console entry: serve the harness. Host/port overridable via env in frieren."""
    import os

    import uvicorn

    host = os.environ.get("ROBOT_HOST", "127.0.0.1")
    port = int(os.environ.get("ROBOT_PORT", "8080"))
    print(f"[robot] control panel at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
