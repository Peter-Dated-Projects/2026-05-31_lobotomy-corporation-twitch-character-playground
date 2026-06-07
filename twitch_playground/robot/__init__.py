"""Robot TTS test harness.

A standalone FastAPI backend + a static control-panel web UI for exercising the
speak/voice-clone feature WITHOUT the pygame playground. It receives mocked chat
events (primarily ``!say``) over HTTP, runs them through the same swear filter
and KokoClone engine the game uses, and plays the audio locally.

Run it with ``frieren run robot`` (see frieren.sh) or directly::

    uv run --group robot python -m twitch_playground.robot.server

This lets us validate "the functionality behind the face" -- the filtering,
voice pairing, synthesis, and playback -- on its own, decoupled from rendering.
"""
