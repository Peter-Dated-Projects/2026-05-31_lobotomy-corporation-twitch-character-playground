---
id: twitch-receive-and-whisper
root: domain
type: domain
status: current
summary: "Twitch receive-chat and bidirectional-whisper research: EventSub channel.chat.message is the current receive path; whisper-as-command-channel is NOT viable (40 unique recipients/day + verified-phone cap), use in-channel commands + Send Chat Message replies instead."
created: 2026-06-02
updated: 2026-06-02
---

# Twitch: Receiving Chat + Bidirectional Whispers as a Command Channel

Research feeding a design decision for the on-screen character playground: can viewers
send commands to the bot via whisper (DM) and get whispered replies, keeping commands
out of public chat? Short answer up front: **receiving is easy; the bidirectional-whisper
command channel is not viable at any real scale.** Use in-channel commands instead.

All facts below are from primary Twitch developer docs (dev.twitch.tv), current as of
June 2026. Where Twitch has deprecated or de-emphasized an older path, it is flagged.

---

## 1. Receiving public chat messages (current path)

There are two ways to read chat: **legacy IRC/TMI** (`irc.chat.twitch.tv`) and
**EventSub `channel.chat.message`** (over WebSocket or webhook).

- **EventSub is the recommended path** as of 2026. Twitch's migration guide says to
  "upgrade your chatbots that are using Twitch IRC to use EventSub (for reading chat
  messages and roomstates) and Twitch API (for sending chat messages)." IRC is "more
  complicated to parse" and has limitations versus EventSub.
  (https://dev.twitch.tv/docs/chat/irc-migration/)
- **IRC is NOT formally deprecated and has no published shutdown date** (as of June 2026).
  The migration guide only *recommends* moving off it; it does not announce an end-of-life.
  Treat IRC as legacy-but-functional: fine for a quick prototype, but build new work on
  EventSub since that is where Twitch is investing and the direction of travel is clear.
  (https://dev.twitch.tv/docs/chat/irc-migration/, https://dev.twitch.tv/docs/chat/irc/)

### `channel.chat.message` scopes + token type

- **Minimum:** `user:read:chat` from the chatting (bot) user.
- **With an App Access Token:** additionally requires `user:bot` from the bot user, plus
  *either* moderator status in the channel *or* `channel:bot` scope granted by the
  broadcaster.
  (https://dev.twitch.tv/docs/chat/irc-migration/, https://dev.twitch.tv/docs/authentication/scopes/)
- **Token type:** works with either a **User Access Token** (bot account) or an
  **App Access Token**. The App-token route is attractive because it sidesteps the
  channel-join rate limits that apply to User-token/IRC connections.

### Subscription / rate-limit cost

- With IRC or with EventSub-via-User-Access-Token, Twitch rate-limits how fast you can
  join channels. **Using an App Access Token for `channel.chat.message`, those
  channel-join limits do not apply** — the main reason to prefer the App-token path for
  a multi-channel bot. (https://dev.twitch.tv/docs/chat/irc-migration/)

### Minimal receive flow (EventSub WebSocket)

1. Connect to the EventSub WebSocket endpoint; receive a `session_welcome` with a session id.
2. `POST https://api.twitch.tv/helix/eventsub/subscriptions` for type `channel.chat.message`,
   with the broadcaster + bot user ids in the condition and the session id as transport.
3. Receive `notification` frames carrying each chat message.
   (https://dev.twitch.tv/docs/eventsub/, https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/)

---

## 2. Receiving whispers (user -> bot) -- CENTRAL QUESTION

### (a) Legacy IRC WHISPER

IRC historically delivered inbound whispers as `WHISPER` messages on the TMI connection.
The current docs steer all whisper handling toward EventSub and the Helix API; the IRC
whisper path is legacy and not documented as the recommended mechanism for new bots.
Do not build on it. (https://dev.twitch.tv/docs/chat/whispers/)

### (b) EventSub `user.whisper.message` ("Whisper Received")

This is the current, recommended way to be notified when the bot account receives a whisper.

- **EventSub type:** `user.whisper.message`.
- **Scope:** `user:read:whispers` *or* `user:manage:whispers`.
- **Token type:** **User Access Token** for the bot account (you must be logged in as the
  account that receives the whispers).
- **Payload** includes sender, recipient, whisper id, and message text.
  (https://dev.twitch.tv/docs/chat/whispers/, https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/)

### Are unsolicited inbound whispers from arbitrary viewers actually deliverable?

**Inbound delivery is the easy half.** A viewer whispering the bot is subject to the
*sender's* whisper limits (see Section 3) — those constrain the viewer, not the bot — and
to per-account whisper privacy settings. The hard anti-spam wall is on the **sending**
side (Section 3), and it bites hardest when the *bot* tries to reply. Receiving a whisper
that a viewer chose to send is generally fine; the design breaks on the reply leg.

---

## 3. Sending whispers (bot -> user) -- THE BOTTLENECK

### Endpoint

- **`POST https://api.twitch.tv/helix/whispers`**
- Query params: `from_user_id`, `to_user_id`. Body: JSON `{ "message": "..." }`.
- **Scope:** `user:manage:whispers`.
- **Token type:** **User Access Token of the *sending* account** (the bot).
  (https://dev.twitch.tv/docs/chat/whispers/)

### Hard prerequisites and gotchas

- **Verified phone number required on the sending account.** "The user sending the whisper
  must have a verified phone number." No phone -> cannot send any whispers. This is a
  per-bot-account setup burden.
- **Blocked / opted-out recipients:** "Some users have disabled the ability to send them
  whispers"; the API returns **HTTP 400** for those. You cannot whisper a user who blocked
  you or disabled stranger-whispers.
- **First-contact length cap:** 500 characters if you've never whispered the target before,
  10,000 once you have an established whisper history.
  (https://dev.twitch.tv/docs/chat/whispers/)

### Rate limits (the killer)

- **Maximum 40 UNIQUE RECIPIENTS PER DAY.** This is the decisive constraint for an
  unsolicited-reply design.
- Within that daily cap: max **3 whispers/second** and **100 whispers/minute**.
- **No elevated limits exist:** "Verified bots do not have higher whisper rate limits, and
  there is no way to get a higher whisper limit."
  (https://dev.twitch.tv/docs/chat/whispers/)

### Is whisper-reply viable at scale?

**No.** Even ignoring the per-account phone-verification setup, the bot can whisper at most
**40 distinct people per day**. A 41st unique viewer who sends a command gets no whisper
reply that day. For an on-stream interactive playground where many distinct viewers issue
commands, 40/day is exhausted almost immediately. The per-second/minute limits are
irrelevant next to the unique-recipient cap.

---

## 4. End-to-end viability of "commands via whisper"

Tying Sections 2 and 3 together: a viewer *can* whisper a command to the bot, and EventSub
*will* deliver it. The design collapses on the **reply leg**:

- The bot account must have a **verified phone number** (per-account setup).
- The bot can whisper back to **at most 40 unique viewers per day**, with no path to raise it.
- Any viewer who blocked the bot or disabled stranger-whispers gets a 400 and no reply.

So the bidirectional channel works for a tiny, fixed audience (e.g. a handful of trusted
operators) but **does not work as a general viewer-facing command channel.** The 40-unique-
recipients/day cap is a hard ceiling Twitch deliberately imposes to stop exactly this kind
of unsolicited fan-out.

---

## 5. Alternatives if whisper-as-command-channel is impractical

| Approach | Mechanism | Scope / token | Reaches all viewers? | Notes |
|---|---|---|---|---|
| **In-channel commands + chat reply** | Read `channel.chat.message` (EventSub); reply with Send Chat Message | read: `user:read:chat`; send: `user:write:chat` (User token; App token also needs `user:bot`) | Yes | Simplest, no caps comparable to whispers. Commands are public, but that is usually fine/desirable for an on-stream toy. |
| **`@mention` reply** | Same as above; just prefix the reply with `@user` | Same | Yes | A convention, not a separate API. |
| **Threaded reply (reply-parent)** | Send Chat Message with `reply_parent_message_id` set to the command message id | Same as Send Chat Message | Yes | Keeps replies visually tied to the command; still public chat. |
| **Channel Points redeem** | Viewer redeems a custom reward; bot reacts to `channel.channel_points_custom_reward_redemption.add` | `channel:read:redemptions` | Yes (redeemers) | Good for a fixed menu of "commands" with built-in cost/cooldown gating; not free-form text. |
| **Whisper channel** | Sections 2-3 | `user:manage:whispers` + verified phone | No (40/day) | Private but capped; only for a tiny operator set. |

Send Chat Message endpoint: `POST https://api.twitch.tv/helix/chat/messages`, supports a
`reply_parent_message_id` parameter for threaded replies.
(https://dev.twitch.tv/docs/chat/send-receive-messages/, https://dev.twitch.tv/docs/api/reference)

Note on scopes: the IRC-era send scope was `chat:edit`; the Helix Send Chat Message endpoint
uses `user:write:chat` (per the IRC migration guide). Use the Helix endpoint + `user:write:chat`
for new work.

---

## Recommendation

- **Receive mechanism: EventSub `channel.chat.message` over WebSocket**, ideally with an
  **App Access Token** (avoids channel-join rate limits and is the path Twitch is investing
  in). Use IRC only for a throwaway prototype, knowing it is legacy.
- **Do NOT build the bidirectional-whisper command channel for viewers.** The 40-unique-
  recipients/day send cap (with no way to raise it) plus the verified-phone prerequisite and
  block/opt-out 400s make whisper replies unworkable for anything beyond a handful of fixed
  operators.
- **Command channel: in-channel chat commands** (e.g. `!join`, `!hug`) read via EventSub,
  with **Send Chat Message** for any reply — optionally using `reply_parent_message_id` to
  thread the response to the originating command, or a leading `@mention`. Commands being
  public is acceptable (and often desirable) for an on-stream character playground.
- If clutter genuinely matters later, **Channel Points redeems** are the clean private-ish
  alternative for a fixed command menu, with built-in cooldown/cost gating — but they are not
  free-form text.
