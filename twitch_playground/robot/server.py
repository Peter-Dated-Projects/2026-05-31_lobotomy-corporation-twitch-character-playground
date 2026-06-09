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

import os
import random
import threading
from pathlib import Path

from dotenv import load_dotenv
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
        # The transient utterance for the renderer's speech balloon: (character,
        # text) while speaking, cleared when the engine stops. Drives the balloon;
        # the persistent robot body comes from server.current_face() so it stays
        # on screen between utterances (see the voice-selection section).
        self.active = None          # tuple[str, str] | None
        self._lock = threading.Lock()

    def is_speaking(self) -> bool:
        eng = self.engine
        return bool(eng and eng.is_speaking)

    def is_playing(self) -> bool:
        """True only while audio is actually playing (not during synthesis)."""
        eng = self.engine
        return bool(eng and eng.is_playing)


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


def _start_redemptions() -> None:
    """Start the Twitch channel-point redemption listener (EventSub WebSocket).

    A redemption's form text (``user_input``) is routed through the SAME speak
    path as the web UI's /api/speak button -- see ``speak_text``. Disabled
    silently if no Twitch credentials are configured.

    Two optional reward ids (discovered from the redemption log) gate behaviour:
      - ``TWITCH_REWARD_ID`` -- the TTS reward. Unset = every reward speaks; set =
        only that reward speaks.
      - ``TWITCH_REWARD_ID_COLOR_CHANGE`` -- the "Change Speaker" reward. When
        set, the voice is locked to one current speaker (first utterance random,
        reused after) and redeeming THIS reward re-rolls it to a DIFFERENT voice;
        the renderer keeps that robot on screen between utterances. When unset,
        each utterance is independently random.
    """
    global _COLOR_CHANGE_REWARD_ID

    # The robot entry points don't load .env on their own (main.py does, for the
    # playground); do it here so auth.ensure_access_token sees the credentials.
    load_dotenv()
    from twitch_playground.chat.eventsub import start_redemption_thread

    tts_reward_id = (os.environ.get("TWITCH_REWARD_ID") or "").strip() or None
    _COLOR_CHANGE_REWARD_ID = (
        os.environ.get("TWITCH_REWARD_ID_COLOR_CHANGE") or ""
    ).strip() or None

    # Change Speaker mode: seed a current speaker now so a robot shows on screen
    # immediately, and the first utterance speaks through this (random) voice.
    if _COLOR_CHANGE_REWARD_ID is not None:
        _reroll_speaker()

    # Delivery filter (None = accept all rewards). With no TTS reward set we
    # accept everything (TTS-for-all), which already includes the change-speaker
    # reward. With one set, we must also let the change-speaker reward through.
    if tts_reward_id is None:
        reward_ids: set[str] | None = None
    else:
        reward_ids = {tts_reward_id}
        if _COLOR_CHANGE_REWARD_ID is not None:
            reward_ids.add(_COLOR_CHANGE_REWARD_ID)

    def _on_redemption(user: str, text: str, rid: str, title: str) -> None:
        # The Change Speaker reward re-rolls the locked voice; it never speaks.
        if _COLOR_CHANGE_REWARD_ID is not None and rid == _COLOR_CHANGE_REWARD_ID:
            new_voice = _reroll_speaker()
            print(f"[robot] {user} redeemed {title!r} -> current speaker is now {new_voice}")
            return
        # Otherwise treat the redemption as a TTS message.
        if not text.strip():
            print(f"[eventsub] {user} redeemed {title!r} with no text; nothing to speak")
            return
        result = speak_text(text, author=user)
        print(
            f"[eventsub] -> speak({result.get('character')}): {result.get('note')} "
            f"| said={result.get('filtered')!r}"
        )

    if start_redemption_thread(_on_redemption, reward_ids=reward_ids) is not None:
        tts_scope = f"tts={tts_reward_id}" if tts_reward_id else "tts=ALL"
        if _COLOR_CHANGE_REWARD_ID:
            mode = f"change_speaker={_COLOR_CHANGE_REWARD_ID} (voice locked to {current_face()})"
        else:
            mode = "no change-speaker reward (voice random per utterance)"
        print(f"[robot] redemption listener started -- {tts_scope}, {mode}")


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_load_engine, name="engine-load", daemon=True).start()
    # Seed an on-screen character immediately so the renderer always has someone
    # to draw -- the face must never be blank, and it only changes on a
    # color-change event (the Change Speaker reward or the dev-UI button).
    if current_face() is None:
        _reroll_speaker()
    _start_redemptions()


# --- speaker selection --------------------------------------------------------
# `_CURRENT_SPEAKER` is the single on-screen character AND the default TTS voice.
# It is persistent: seeded once at startup so a face always shows, reused for
# every utterance, and changed ONLY by a color-change event -- either the Twitch
# "Change Speaker" reward (TWITCH_REWARD_ID_COLOR_CHANGE) or the dev-UI button
# (POST /api/change-speaker). Speaking never changes who is on screen.
_SPEAKER_LOCK = threading.Lock()
_COLOR_CHANGE_REWARD_ID: str | None = None  # set at startup from the env
_CURRENT_SPEAKER: str | None = None           # the on-screen character == default voice


def _random_voice() -> str:
    return random.choice(settings.ROBOT_ROSTER)


def _choose_voice() -> str:
    """The voice for a TTS utterance: always the persistent current speaker.

    Seeds it once if somehow still unset (startup normally seeds it). Speaking
    does NOT re-roll the speaker -- the on-screen character only changes on a
    color-change event (see :func:`change_speaker`)."""
    global _CURRENT_SPEAKER
    with _SPEAKER_LOCK:
        if _CURRENT_SPEAKER is None:
            _CURRENT_SPEAKER = _random_voice()
        return _CURRENT_SPEAKER


def _reroll_speaker() -> str:
    """Pick a NEW current speaker (different from the current one when possible)
    and return it. This is the color-change event: triggered by the Change
    Speaker reward, the dev-UI button, and once at startup to seed the face."""
    global _CURRENT_SPEAKER
    with _SPEAKER_LOCK:
        others = [v for v in settings.ROBOT_ROSTER if v != _CURRENT_SPEAKER]
        _CURRENT_SPEAKER = random.choice(others or list(settings.ROBOT_ROSTER))
        return _CURRENT_SPEAKER


def change_speaker(character: str | None = None) -> str:
    """Color-change event: switch the on-screen character.

    With *character* given (and valid), switch to it exactly; otherwise re-roll
    to a random different one. Returns the new current speaker."""
    global _CURRENT_SPEAKER
    if character is not None and character in settings.ROBOT_ROSTER:
        with _SPEAKER_LOCK:
            _CURRENT_SPEAKER = character
            return _CURRENT_SPEAKER
    return _reroll_speaker()


def current_face() -> str | None:
    """The character the renderer keeps on screen. Seeded at startup and changed
    only by a color-change event, so it is non-None for the renderer's whole
    lifetime and never flips on its own between utterances."""
    return _CURRENT_SPEAKER


# --- API ---------------------------------------------------------------------


class SpeakRequest(BaseModel):
    text: str
    character: str | None = None   # explicit voice; if omitted, a random one is chosen
    author: str = "webui"          # mock username (for logging; does not pick the voice)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": STATE.status,
        "detail": STATE.detail,
        "device": STATE.device,
        "roster": settings.ROBOT_ROSTER,
        "is_speaking": STATE.is_speaking(),
        "is_playing": STATE.is_playing(),  # audio actually audible right now
        "speaker": current_face(),         # persistent on-screen character
    }


@app.get("/api/roster")
def roster() -> dict:
    return {"roster": settings.ROBOT_ROSTER}


class ChangeSpeakerRequest(BaseModel):
    character: str | None = None  # switch to this exact character; omit to re-roll


@app.post("/api/change-speaker")
def change_speaker_endpoint(req: ChangeSpeakerRequest | None = None) -> dict:
    """Color-change event: switch the on-screen character. The dev-UI emitter and
    the Twitch Change Speaker reward both land here (the reward via its listener)."""
    requested = req.character if req is not None else None
    speaker = change_speaker(requested)
    return {"ok": True, "speaker": speaker}


def speak_text(text: str, *, character: str | None = None, author: str = "webui") -> dict:
    """Truncate, filter, choose a voice, and (when the engine is ready) speak.

    The voice is *character* if given (the web UI's per-Sephirah buttons), else a
    random roster voice picked per utterance. Shared by the /api/speak web button
    and the channel-point redemption listener so both drive the face identically.
    Always returns the filtered text + chosen voice so the caller can report the
    result even in dry mode. *author* is retained for logging only.
    """
    text = (text or "").strip()[: settings.SPEAK_MAX_MESSAGE_LEN]
    if not text:
        return {"ok": False, "error": "empty message"}

    filtered = filter_message(text)
    character = character or _choose_voice()
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


@app.post("/api/speak")
def speak(req: SpeakRequest) -> dict:
    """Receive a mocked !say event from the web UI and speak it."""
    return speak_text(req.text, character=req.character, author=req.author)


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
