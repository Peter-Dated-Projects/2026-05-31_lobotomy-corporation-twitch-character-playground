"""Twitch token lifecycle: validate the stored access token at startup and, if
it has expired (or is about to), transparently refresh it.

The token pair lives in ``.env`` as ``TWITCH_ACCESS_TOKEN`` / ``TWITCH_REFRESH_TOKEN``
and was minted by twitchtokengenerator.com. Those tokens are bound to *its* OAuth
app -- it holds the client secret -- so a refresh goes through its proxy endpoint
rather than Twitch's ``/oauth2/token`` directly. That is why we need no client id
or secret on our side. A successful refresh is written back to ``.env`` so it
persists across restarts.

Pure stdlib HTTP (urllib) so this adds no dependency; the calls are one-shot and
run on the main thread before the listener thread starts.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
REFRESH_URL = "https://twitchtokengenerator.com/api/refresh/"

ACCESS_VAR = "TWITCH_ACCESS_TOKEN"
REFRESH_VAR = "TWITCH_REFRESH_TOKEN"

# If a still-valid token has less than this many seconds of life left, refresh it
# now rather than risk it dying mid-session (Twitch user tokens can be short).
REFRESH_MARGIN = 3600


def _strip(token: str) -> str:
    """twitchtokengenerator/Twitch want the bare token; tolerate an ``oauth:``
    prefix in case it was pasted in IRC form."""
    return token.replace("oauth:", "").strip()


def validate(access_token: str) -> dict | None:
    """Return the validate payload (``login``, ``expires_in``, ``scopes``) if the
    token is live, else ``None``. A 401 means expired/invalid; network failures
    are also treated as "not usable" so the caller falls back gracefully."""
    req = urllib.request.Request(
        VALIDATE_URL, headers={"Authorization": f"OAuth {_strip(access_token)}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError:
        return None  # 401 -> expired/invalid
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[auth] validate failed (network): {exc}")
        return None


def refresh(refresh_token: str) -> tuple[str, str] | None:
    """Exchange the refresh token for a fresh ``(access, refresh)`` pair via
    twitchtokengenerator. Returns ``None`` if the refresh is rejected. The new
    refresh token may differ from the old one (rotation), so we return both."""
    url = REFRESH_URL + urllib.parse.quote(_strip(refresh_token), safe="")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"[auth] refresh request failed: {exc}")
        return None
    if not data.get("success"):
        print(f"[auth] refresh rejected: {data.get('message', data)}")
        return None
    new_access = data.get("token")
    if not new_access:
        print("[auth] refresh response contained no token")
        return None
    # twitchtokengenerator usually returns the same refresh token; keep the old
    # one if it omits a replacement.
    new_refresh = data.get("refresh") or _strip(refresh_token)
    return new_access, new_refresh


def _persist(access: str, refresh_token: str) -> None:
    """Write the refreshed pair back to ``.env`` and into the live process env so
    the new tokens survive a restart and are visible to the rest of this run."""
    os.environ[ACCESS_VAR] = access
    os.environ[REFRESH_VAR] = refresh_token
    try:
        from dotenv import find_dotenv, set_key
    except ImportError:
        print("[auth] python-dotenv missing; refreshed tokens won't persist to .env")
        return
    path = find_dotenv(usecwd=True)
    if not path:
        print("[auth] no .env found; refreshed tokens won't persist")
        return
    # quote_mode="never": tokens are URL-safe, keep the file diff clean.
    set_key(path, ACCESS_VAR, access, quote_mode="never")
    set_key(path, REFRESH_VAR, refresh_token, quote_mode="never")


def _do_refresh(refresh_token: str) -> str | None:
    """Refresh, persist, and re-validate. Returns the new access token, or
    ``None`` if any step fails."""
    result = refresh(refresh_token)
    if result is None:
        return None
    new_access, new_refresh = result
    _persist(new_access, new_refresh)
    info = validate(new_access)
    if info is None:
        print("[auth] refreshed token failed validation")
        return None
    print(
        f"[auth] refreshed; valid as {info.get('login', '?')} "
        f"({info.get('expires_in', '?')}s left)"
    )
    return new_access


def ensure_access_token() -> str | None:
    """Return a usable Twitch access token, refreshing and persisting if needed.

    ``None`` means we have no working credentials -- the caller should fall back
    to dev mode. The flow: validate the stored access token; if it is live (and
    not about to expire) use it; if it is live but expiring soon, refresh early
    but fall back to the still-valid token if that fails; if it is dead, refresh.
    """
    access = os.environ.get(ACCESS_VAR)
    refresh_token = os.environ.get(REFRESH_VAR)
    if not access:
        return None

    info = validate(access)
    if info is not None:
        # Twitch reports expires_in=0 for tokens that carry no expiry; treat that
        # (and a missing field) as "no expiry" rather than "expires immediately".
        secs = info.get("expires_in") or 0
        login = info.get("login", "?")
        life = f"{secs}s left" if secs else "no expiry"
        if secs and secs < REFRESH_MARGIN and refresh_token:
            print(f"[auth] token valid as {login} but expires in {secs}s; refreshing early")
            refreshed = _do_refresh(refresh_token)
            if refreshed:
                return refreshed
            print(f"[auth] early refresh failed; using current token ({secs}s left)")
        else:
            print(f"[auth] token valid as {login} ({life})")
        return access

    # Stored access token is expired/invalid -> the refresh token is our only hope.
    if not refresh_token:
        print("[auth] access token invalid and no refresh token; entering dev mode")
        return None
    print("[auth] access token expired; refreshing...")
    refreshed = _do_refresh(refresh_token)
    if refreshed:
        return refreshed
    print("[auth] refresh failed; entering dev mode")
    return None
