"""EventSub WebSocket listener for Channel Points custom-reward redemptions.

This is the channel-points counterpart to ``chat/bot.py`` (which reads IRC chat).
Two facts force this shape:

- Channel-point redemptions never arrive over IRC, and Twitch decommissioned the
  old PubSub channel-points path in April 2025. The only live mechanism is
  **EventSub**, subscription type
  ``channel.channel_points_custom_reward_redemption.add``.
- twitchio 2.x (pinned ``<3`` here) only ships a *webhook* EventSub ext, which
  needs a public HTTPS callback. So this is a small standalone EventSub
  **WebSocket** client built on ``aiohttp`` (already pulled in by twitchio) -- it
  needs no public endpoint and runs fine on the local streaming PC.

It runs on its own daemon thread and calls ``on_redemption(user, text, reward_id,
reward_title)`` for each redemption whose reward id is in the caller-supplied
``reward_ids`` set (pass ``None`` to deliver every reward). EVERY redemption is
logged with its ``reward_id`` regardless, so you can discover which ids to filter
on. The robot server builds the set from ``TWITCH_REWARD_ID`` /
``TWITCH_REWARD_ID_COLOR_CHANGE`` and routes by id inside its handler.

Auth: requires a **broadcaster** user token carrying ``channel:read:redemptions``
(the same ``.env`` ``TWITCH_ACCESS_TOKEN`` / ``TWITCH_REFRESH_TOKEN``, regenerated
with that scope added). The broadcaster user id and the token's client id are
both read from Twitch's ``/oauth2/validate`` response, so no extra config beyond
the token (and optional ``TWITCH_REWARD_ID``) is needed.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Callable, Optional

import aiohttp

from twitch_playground.chat import auth

# EventSub WebSocket entrypoint and the Helix endpoint that creates subscriptions.
WS_URL = "wss://eventsub.wss.twitch.tv/ws"
HELIX_SUBSCRIPTIONS = "https://api.twitch.tv/helix/eventsub/subscriptions"

SUB_TYPE = "channel.channel_points_custom_reward_redemption.add"
SUB_VERSION = "1"
REQUIRED_SCOPE = "channel:read:redemptions"

# Hard cap on the redeemer's input text before it reaches the handler (TTS). Long
# inputs would make the spoken clip drag on; truncate rather than reject so a
# slightly-too-long message still speaks.
MAX_INPUT_LEN = 255

# on_redemption(user_login, user_input, reward_id, reward_title) -> None
RedemptionHandler = Callable[[str, str, str, str], None]


async def _subscribe(
    session: aiohttp.ClientSession,
    token: str,
    client_id: str,
    broadcaster_id: str,
    session_id: str,
) -> bool:
    """Create the redemption subscription bound to this WebSocket session.

    One subscription covers ALL custom rewards on the channel; per-reward
    filtering happens when notifications arrive (see ``_handle_notification``).
    """
    body = {
        "type": SUB_TYPE,
        "version": SUB_VERSION,
        "condition": {"broadcaster_user_id": broadcaster_id},
        "transport": {"method": "websocket", "session_id": session_id},
    }
    headers = {
        "Authorization": f"Bearer {auth._strip(token)}",
        "Client-Id": client_id,
        "Content-Type": "application/json",
    }
    async with session.post(HELIX_SUBSCRIPTIONS, json=body, headers=headers) as resp:
        text = await resp.text()
        if resp.status in (200, 202):
            print("[eventsub] subscribed to channel-point redemptions; waiting for redeems")
            return True
        # 403 here almost always means the token is missing channel:read:redemptions
        # or is not the broadcaster's token; surface the body so it's diagnosable.
        print(f"[eventsub] subscription FAILED (HTTP {resp.status}): {text}")
        return False


def _handle_notification(
    data: dict, on_redemption: RedemptionHandler, reward_ids: Optional[set[str]]
) -> None:
    """Log every redemption in full (always) and invoke the handler on a match.

    Two log lines are emitted per redemption: a readable summary of the most
    useful fields, then the complete event payload as JSON so NOTHING Twitch
    sent is lost (broadcaster ids, reward prompt/cost/cooldown, status,
    redeemed_at, the untruncated user_input, etc.). This is the discovery path
    for finding a reward's id to set TWITCH_REWARD_ID.
    """
    if data.get("metadata", {}).get("subscription_type") != SUB_TYPE:
        return
    event = data.get("payload", {}).get("event", {})
    reward = event.get("reward", {}) or {}
    rid = reward.get("id", "")
    title = reward.get("title", "")
    user = event.get("user_login") or event.get("user_name") or "anonymous"
    user_input = (event.get("user_input", "") or "")[:MAX_INPUT_LEN]

    matched = reward_ids is None or rid in reward_ids
    verdict = "delivered to handler" if matched else "ignored (reward not in filter)"
    print(
        "[eventsub] redemption | "
        f"redemption_id={event.get('id', '')} | reward_id={rid} | title={title!r} | "
        f"cost={reward.get('cost')} | user={user} (id={event.get('user_id', '')}) | "
        f"status={event.get('status', '')} | redeemed_at={event.get('redeemed_at', '')} | "
        f"input={user_input!r} | {verdict}"
    )
    # Full payload dump: one JSON object per line so every field is captured and
    # the log stays grep-friendly (one record per line).
    print(f"[eventsub] redemption metadata: {json.dumps(event, ensure_ascii=False, sort_keys=True)}")

    if matched:
        try:
            on_redemption(user, user_input, rid, title)
        except Exception as exc:  # never let a handler error kill the listener
            print(f"[eventsub] on_redemption handler error: {type(exc).__name__}: {exc}")


async def _consume(
    ws: aiohttp.ClientWebSocketResponse,
    session: aiohttp.ClientSession,
    token: str,
    client_id: str,
    broadcaster_id: str,
    on_redemption: RedemptionHandler,
    reward_ids: Optional[set[str]],
) -> Optional[str]:
    """Drain one WebSocket connection. Returns a reconnect URL if Twitch asked us
    to migrate (``session_reconnect``), else ``None`` when the socket closes."""
    async for msg in ws:
        if msg.type is not aiohttp.WSMsgType.TEXT:
            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break
            continue

        data = json.loads(msg.data)
        mtype = data.get("metadata", {}).get("message_type")
        if mtype == "session_welcome":
            session_id = data["payload"]["session"]["id"]
            await _subscribe(session, token, client_id, broadcaster_id, session_id)
        elif mtype == "session_reconnect":
            # Twitch is rotating the edge; reconnect to the provided URL and
            # re-use the existing subscriptions (no re-subscribe needed).
            return data["payload"]["session"]["reconnect_url"]
        elif mtype == "notification":
            _handle_notification(data, on_redemption, reward_ids)
        elif mtype == "revocation":
            print(f"[eventsub] subscription revoked: {data.get('payload')}")
        # session_keepalive: nothing to do (presence proves the socket is alive)
    return None


async def _run(
    token: str,
    client_id: str,
    broadcaster_id: str,
    on_redemption: RedemptionHandler,
    reward_ids: Optional[set[str]],
) -> None:
    """Connect, subscribe, and consume forever, reconnecting with backoff."""
    backoff = 1
    url = WS_URL
    session = aiohttp.ClientSession()
    try:
        while True:
            reconnect_url: Optional[str] = None
            try:
                async with session.ws_connect(url, heartbeat=None) as ws:
                    backoff = 1  # a successful connect resets the backoff
                    reconnect_url = await _consume(
                        ws, session, token, client_id, broadcaster_id,
                        on_redemption, reward_ids,
                    )
            except aiohttp.ClientError as exc:
                print(f"[eventsub] connection error: {exc}")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[eventsub] unexpected error: {type(exc).__name__}: {exc}")

            if reconnect_url:
                url = reconnect_url  # migrate immediately, no backoff
                continue
            url = WS_URL
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
    finally:
        await session.close()


def start_redemption_thread(
    on_redemption: RedemptionHandler, reward_ids: Optional[set[str]] = None
) -> Optional[threading.Thread]:
    """Start the EventSub redemption listener on a daemon thread.

    Returns the thread, or ``None`` if Twitch credentials are absent/invalid (the
    caller then simply runs without channel-point support). ``reward_ids``, if
    given, gates ``on_redemption`` to redemptions whose reward id is in the set;
    ``None`` delivers every reward. All redemptions are logged regardless so the
    correct ids can be discovered.
    """
    token = auth.ensure_access_token()
    if not token:
        print("[eventsub] no usable TWITCH_ACCESS_TOKEN; redemption listener disabled")
        return None

    info = auth.validate(token)
    if not info:
        print("[eventsub] token failed validation; redemption listener disabled")
        return None

    client_id = info.get("client_id")
    broadcaster_id = info.get("user_id")
    scopes = info.get("scopes") or []
    if not client_id or not broadcaster_id:
        print("[eventsub] validate response missing client_id/user_id; disabled")
        return None
    if REQUIRED_SCOPE not in scopes:
        # Subscribing will 403, but we still try so the failure is loud and clear.
        print(
            f"[eventsub] WARNING: token is missing the '{REQUIRED_SCOPE}' scope -- "
            "redemptions will NOT be delivered until you regenerate the token with "
            f"it. Current scopes: {scopes}"
        )

    def _thread() -> None:
        # twitchio's bot uses the same pattern: give this daemon thread its own
        # event loop before running the asyncio client.
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(
            _run(token, client_id, broadcaster_id, on_redemption, reward_ids)
        )

    thread = threading.Thread(target=_thread, name="eventsub-redemptions", daemon=True)
    thread.start()
    return thread
