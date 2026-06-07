#!/usr/bin/env bash
# frieren.sh -- project entrypoint for the Lobotomy Corp Twitch playground.
# Usage: ./frieren.sh <command>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PYTHONUNBUFFERED=1

ENV_FILE="$ROOT/.env"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Open a URL in the default browser, across the platforms this repo runs on
# (Git Bash/WSL on Windows, macOS, Linux). Best-effort: prints the URL if it
# can't auto-open so the user can copy it.
_open_url() {
    local url="$1"
    # Windows (Git Bash / MSYS / WSL): PowerShell's Start-Process is the most
    # reliable opener and returns a clean exit code. Avoid `cmd.exe /c start` --
    # MSYS path-converts the `/c` and the call silently breaks.
    if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "Start-Process '$url'" >/dev/null 2>&1 && return 0
    fi
    if command -v xdg-open >/dev/null 2>&1; then       # Linux
        xdg-open "$url" >/dev/null 2>&1 && return 0
    fi
    if command -v open >/dev/null 2>&1; then           # macOS
        open "$url" >/dev/null 2>&1 && return 0
    fi
    if command -v explorer.exe >/dev/null 2>&1; then    # Windows fallback
        # explorer.exe opens the URL but exits 1 even on success; best-effort.
        explorer.exe "$url" >/dev/null 2>&1 || true
        return 0
    fi
    echo "    (couldn't open a browser automatically -- open this URL manually:)"
    echo "    $url"
}

# Ensure .env exists, seeding it from .env.example on first run.
_ensure_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ROOT/.env.example" ]; then
            cp "$ROOT/.env.example" "$ENV_FILE"
            echo "    created .env from .env.example"
        else
            : > "$ENV_FILE"
        fi
    fi
}

# _set_env_var KEY VALUE -- replace KEY=... in .env, or append it if absent.
# Uses awk (not sed -i) to stay portable across GNU/BSD and to avoid escaping
# pitfalls with token characters.
_set_env_var() {
    local key="$1" value="$2" tmp
    _ensure_env_file
    tmp="$(mktemp)"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        awk -v k="$key" -v v="$value" \
            'BEGIN{FS="="} $1==k {print k"="v; next} {print}' "$ENV_FILE" > "$tmp"
    else
        cat "$ENV_FILE" > "$tmp"
        printf '%s=%s\n' "$key" "$value" >> "$tmp"
    fi
    mv "$tmp" "$ENV_FILE"
}

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

# Open twitchtokengenerator, wait for the user to paste the generated tokens,
# and write them straight into .env. The token MUST be minted by the BROADCASTER
# account with the channel:read:redemptions scope or Channel Point redemptions
# (the robot TTS) will 403. See chat/eventsub.py and chat/auth.py.
cmd_token() {
    local url="https://twitchtokengenerator.com/"
    echo "==> Twitch token setup"
    echo "    Opening the token generator in your browser..."
    echo "    1. Choose 'Custom Scope Token'."
    echo "    2. Sign in as the BROADCASTER account and select these scopes:"
    echo "         chat:edit   chat:read   user:read:chat   channel:read:redemptions"
    echo "    3. Generate + authorize, then copy the Access Token and Refresh Token."
    echo
    _open_url "$url"
    echo

    local access refresh
    printf "    Paste ACCESS token (blank to skip):  "
    read -r access || true
    access="$(printf '%s' "${access:-}" | tr -d '[:space:]')"
    if [ -z "$access" ]; then
        echo "    no token entered -- .env left unchanged."
        return 0
    fi
    printf "    Paste REFRESH token (blank to skip): "
    read -r refresh || true
    refresh="$(printf '%s' "${refresh:-}" | tr -d '[:space:]')"

    _set_env_var TWITCH_ACCESS_TOKEN "$access"
    if [ -n "$refresh" ]; then
        _set_env_var TWITCH_REFRESH_TOKEN "$refresh"
    fi
    echo "    wrote token(s) to .env"
}

cmd_setup() {
    echo "==> First-run setup..."
    echo "    syncing playground + robot deps (base + robot group)..."
    # --group robot installs the playground's base deps AND the robot harness
    # (fastapi/uvicorn). yt-dlp ships in the base deps, so the voice-build tool
    # is provided too; only ffmpeg remains a system prerequisite (see below).
    uv sync --group robot
    if ! command -v ffmpeg >/dev/null 2>&1; then
        echo "    warn: ffmpeg not found on PATH -- needed by './frieren.sh voices'." >&2
        echo "          Install it (e.g. 'choco install ffmpeg' / 'brew install ffmpeg')." >&2
    fi

    # Offer the interactive Twitch token step (opens the browser + writes .env).
    echo
    printf "==> Configure the Twitch token now? Opens a browser. [y/N] "
    local ans
    read -r ans || true
    case "${ans:-}" in
        [Yy]*) cmd_token ;;
        *)     echo "    skipped -- run './frieren.sh token' later to set it up." ;;
    esac

    cat <<EOF

Setup done. Next steps:
  - Voice clips are gitignored; build them with (needs ffmpeg on PATH):
      ./frieren.sh voices
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
  token                     Open twitchtokengenerator + write tokens into .env
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
    token)          cmd_token ;;
    test)           cmd_test ;;
    clean)          cmd_clean ;;
    help|--help|-h) cmd_help ;;
    *)
        echo "Unknown command: ${1:-}" >&2
        cmd_help >&2
        exit 1
        ;;
esac
