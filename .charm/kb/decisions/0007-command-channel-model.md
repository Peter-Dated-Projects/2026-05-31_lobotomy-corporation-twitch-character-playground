---
id: 0007-command-channel-model
root: decisions
type: decision
status: current
summary: "Commands arrive as free in-channel chat commands (e.g. !join) read via EventSub channel.chat.message; the whisper-as-command-channel idea is rejected (Twitch caps sends at 40 unique recipients/day). Channel Points redeems are reserved for future opt-in gated actions, and !join itself may become points-gated later."
related:
  - domain/twitch-receive-and-whisper
created: 2026-06-02
updated: 2026-06-02
---

# Command channel model

How viewers drive the on-screen character playground from Twitch.

## Decision

- **Receive via EventSub `channel.chat.message`** (WebSocket; ideally an App Access
  Token to avoid channel-join rate limits). IRC/TMI is legacy-but-functional and
  acceptable only for a throwaway prototype.
- **`!join` is a free, public, in-channel command** (it spawns the viewer's
  character). Anyone can type it; the bot
  reacts on-screen. Commands being visible in chat is fine (often desirable) for an
  on-stream toy.
- **Channel Points redeems are reserved for future opt-in actions.** No such actions
  are defined yet -- this is recorded intent, not implemented behavior. Channel Points
  are the chosen mechanism when we later want cost/cooldown-gated actions (built-in
  gating, private-ish, fixed menu rather than free-form text).
- **`!join` may itself become Channel-Points-gated later** (i.e. spawning costs
  points). Open intent; not built.

## Why not whispers

The original idea was a two-way whisper (DM) command channel to keep chat clean.
It does not work for a viewer-facing audience: Twitch's Helix Send Whisper endpoint
caps the sending account at **40 unique recipients per day with no way to raise it**
(verified bots included), plus a verified-phone prerequisite and HTTP 400s for
blocked / stranger-whisper-disabled users. The 41st distinct viewer in a day gets no
reply. Receiving whispers is fine; the reply leg is the hard wall. Full analysis:
[twitch-receive-and-whisper](../domain/twitch-receive-and-whisper.md).

## Future actions (intent log)

No gated actions are specified yet. When they are, define them against the Channel
Points path above and update this note. Candidate seed: spawning costs points.
