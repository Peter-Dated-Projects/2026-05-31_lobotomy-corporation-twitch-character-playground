#!/usr/bin/env bash
# frieren.sh -- project entrypoint for the Lobotomy Corp Twitch playground.
# Usage: ./frieren.sh <command>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_run() {
    local target="${2:-help}"
    case "$target" in
        playground)
            # The full pygame playground (crowd + sim). The speak/voice feature
            # is gated by SPEAK_ENABLED (off by default); set it to turn it on.
            echo "==> Running playground..."
            uv run playground
            ;;
        robot)
            # The robot face renderer: a pygame window drawing only the speaking
            # Sephirah + balloon, with the speak backend on a background thread.
            # Open the control panel URL it prints to drive it.
            echo "==> Running robot renderer (+ control panel backend)..."
            uv run --group robot robot
            ;;
        robot-debug)
            # Headless web control panel only -- no face window. Fire mocked
            # !say events from the browser to test filtering + voice.
            echo "==> Running robot debug control panel (headless)..."
            uv run --group robot robot-debug
            ;;
        *)
            echo "Usage: ./frieren.sh run playground|robot|robot-debug" >&2
            return 1
            ;;
    esac
}

cmd_setup() {
    echo "==> First-run setup..."
    echo "    syncing base + robot deps..."
    uv sync --group robot
    cat <<EOF

Setup done. Next steps:
  - Voice clips are gitignored; build them with:
      uv run scripts/setup_voices.py
  - Run the game:        ./frieren.sh run playground
  - Run the robot face:  ./frieren.sh run robot
  - Run the web panel:   ./frieren.sh run robot-debug
EOF
}

cmd_test() {
    echo "==> Running tests..."
    uv run pytest -q
}

cmd_voices() {
    # Build/rebuild the reference voice WAVs from the dub clips (yt-dlp + ffmpeg).
    echo "==> Building reference voices..."
    uv run scripts/setup_voices.py "${@:2}"
}

cmd_clean() {
    echo "==> Removing build artifacts..."
    find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name ".DS_Store" -delete 2>/dev/null || true
}

cmd_help() {
    cat <<EOF
Usage: ./frieren.sh <command>

Commands:
  run playground            Run the full pygame playground
  run robot                 Run the robot face renderer + control-panel backend
  run robot-debug           Run the headless web control panel only
  voices [args]             Build reference voice WAVs (passes args to setup_voices.py)
  setup                     First-run setup (uv sync --group robot)
  test                      Run the test suite
  clean                     Remove build artifacts (__pycache__, *.pyc, .DS_Store)
  help                      Show this message
EOF
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

case "${1:-help}" in
    run)            cmd_run "$@" ;;
    voices)         cmd_voices "$@" ;;
    setup)          cmd_setup ;;
    test)           cmd_test ;;
    clean)          cmd_clean ;;
    help|--help|-h) cmd_help ;;
    *)
        echo "Unknown command: ${1:-}" >&2
        cmd_help >&2
        exit 1
        ;;
esac
