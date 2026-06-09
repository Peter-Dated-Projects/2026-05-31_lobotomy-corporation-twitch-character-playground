#!/usr/bin/env bash
# frieren.sh -- project entrypoint for the Lobotomy Corp Twitch playground.
# Usage: ./frieren.sh <command>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export PYTHONUNBUFFERED=1

ENV_FILE="$ROOT/.env"
VOICES_DIR="$ROOT/twitch_playground/assets/voices"
# Prebuilt reference voice clips, published as a GitHub release asset so a fresh
# machine can bootstrap without yt-dlp + YouTube + ffmpeg. Bump the tag here when
# the clips are rebuilt (see scripts/setup_voices.py + './frieren.sh voices').
VOICES_RELEASE_URL="https://github.com/Peter-Dated-Projects/2026-05-31_lobotomy-corporation-twitch-character-playground/releases/download/voices-v1/voices.zip"

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

# Download the prebuilt reference voice clips from the GitHub release and unzip
# them into VOICES_DIR. Lets a fresh machine bootstrap voices without yt-dlp +
# YouTube + ffmpeg. Returns non-zero (without exiting the script) on any failure
# so callers can fall back to the from-source build.
_fetch_voices() {
    local tmp
    if ! command -v unzip >/dev/null 2>&1; then
        echo "    error: 'unzip' not found on PATH -- cannot install prebuilt clips." >&2
        return 1
    fi
    mkdir -p "$VOICES_DIR"
    tmp="$(mktemp -d)"
    echo "    downloading prebuilt voice clips..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$VOICES_RELEASE_URL" -o "$tmp/voices.zip" || {
            echo "    error: download failed ($VOICES_RELEASE_URL)." >&2; rm -rf "$tmp"; return 1; }
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$VOICES_RELEASE_URL" -O "$tmp/voices.zip" || {
            echo "    error: download failed ($VOICES_RELEASE_URL)." >&2; rm -rf "$tmp"; return 1; }
    else
        echo "    error: neither curl nor wget found on PATH." >&2; rm -rf "$tmp"; return 1
    fi
    if ! unzip -o -q "$tmp/voices.zip" -d "$VOICES_DIR"; then
        echo "    error: unzip failed." >&2; rm -rf "$tmp"; return 1
    fi
    rm -rf "$tmp"
    echo "    voice clips installed -> $VOICES_DIR"
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
        sephirah)
            # Sephirah character renderer: shows a full-screen portrait of
            # Angela/Hod/Yesod/Netzach/Malkuth that bobs while speaking, plus a
            # speech balloon. Open the control panel URL it prints to pick a
            # character + speak.
            echo "==> Running Sephirah character renderer (+ control panel backend)..."
            uv run --group robot python -m twitch_playground.robot.sephirah_renderer
            ;;
        *)
            echo "Usage: ./frieren.sh run playground|robot|robot-debug|sephirah" >&2
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
    # Never let the token step abort setup: declining, closing the browser, or
    # any failure inside cmd_token must still fall through to the next steps.
    case "${ans:-}" in
        [Yy]*) cmd_token || echo "    token step skipped (incomplete) -- run './frieren.sh token' later." ;;
        *)     echo "    skipped -- run './frieren.sh token' later to set it up." ;;
    esac

    # Offer the prebuilt voice clips (no yt-dlp/ffmpeg needed). Failure here must
    # not abort setup -- the user can still build from source afterwards.
    echo
    printf "==> Download prebuilt voice clips now? [Y/n] "
    local vans
    read -r vans || true
    case "${vans:-}" in
        [Nn]*) echo "    skipped -- fetch later with './frieren.sh voices --fetch', or build from source with './frieren.sh voices'." ;;
        *)     _fetch_voices || echo "    voice fetch failed -- run './frieren.sh voices --fetch' later." ;;
    esac

    cat <<EOF

Setup done. Next steps:
  - Voice clips: fetched above if you chose to; otherwise
      ./frieren.sh voices --fetch   (prebuilt download, no ffmpeg)
      ./frieren.sh voices           (rebuild from source; needs yt-dlp + ffmpeg)
  - Run the game:        ./frieren.sh run playground
  - Run the robot face:       ./frieren.sh run robot
  - Run the Sephirah faces:   ./frieren.sh run sephirah
  - Run the web panel:        ./frieren.sh run robot-debug
EOF
}

cmd_test() {
    echo "==> Running tests..."
    uv run pytest -q
}

cmd_voices() {
    # `--fetch` pulls the prebuilt clips from the GitHub release (no yt-dlp /
    # ffmpeg needed). Otherwise build/rebuild from the dub source via
    # setup_voices.py, passing through any extra args (e.g. --only hod, --force).
    if [ "${2:-}" = "--fetch" ]; then
        echo "==> Fetching prebuilt reference voices..."
        _fetch_voices
        return
    fi
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
  run sephirah              Run the Sephirah character renderer (named faces + mouth anim)
  voices --fetch            Download prebuilt reference voice clips (no yt-dlp/ffmpeg)
  voices [args]             Build reference voices from source (passes args to setup_voices.py)
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
