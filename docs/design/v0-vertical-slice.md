# v0 Design: Thinnest Vertical Slice

The goal of v0 is to prove the entire pipeline end-to-end as fast as possible:
real Twitch chat -> command -> a character appears in a pygame scene, wanders,
and responds to `!hug` / `!follow`. Everything else is deferred until this works.

This document covers the decisions the research briefs did NOT settle (product
scope, the behavior/state model for follow+hug, and the asset abstraction). For
the mechanics of rendering, steering, and IRC, see the existing research briefs
under `docs/research/` and `research/`.

---

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deployment | Standalone pygame window, captured by Streamlabs as a Window Capture source | Simplest path; no transparency/chroma-key complexity for v0 |
| Scene | Visible "scene box" with an opaque background (a real backdrop, not transparent) | A normal window capture in a corner of the layout; no filters needed |
| Render rate | pygame capped at 12 fps via `clock.tick(12)` | Deliberate low-fps / stop-motion aesthetic. All movement is delta-time based so the cap can be raised later without changing motion physics. Streamlabs capture rate is independent of this |
| Render method (v0) | Plain full-surface blit + y-sort each frame | At a few dozen sprites in a 960x540 box this is trivially cheap. Dirty-rect/`LayeredDirty` is premature; add only if profiling demands it |
| Assets | Procedural placeholder sprites behind a clean provider interface | Real LC sprites are not extracted yet. The provider seam decouples the whole build from the asset-extraction track |
| Identity | Username nameplate above each character | Viewers must be able to find themselves |
| Chat library | twitchio, pinned to 2.x (`>=2.10,<3`) | See risks — 3.x changed the API and auth model substantially |
| Threading | twitchio on a daemon thread, `queue.Queue` drained each frame | Per research; pygame stays single-threaded on the main thread |

---

## Command surface (v0)

| Command | Effect |
|---|---|
| `!join` | Spawn a character bound to the sender's username. If already present, resets the idle timer. Returns the character to WANDER if it was grouped. |
| `!hug @user` | One-shot hug emote played on both the sender and the target. Returns both to their prior behavior afterward. |
| `!follow @user` | Sender leaves WANDER, walks to the target's group, and stands idle beside them. |
| `!leave` | Sender leaves any group and returns to WANDER. |

Targeting rules: `@` is stripped and the name lowercased. Self-targeting
(`!hug` yourself) and commands against an absent user are no-ops. A first
interaction does NOT auto-spawn in v0 — you must `!join` first (keeps the loop
explicit and simple).

> Open interpretation to confirm: `!follow` is treated as one-directional —
> the sender joins the target's standing cluster immediately, no mutual consent
> required. If you want follow to require both sides to opt in, that's a small
> change to the grouping logic.

---

## Behavior / state model

This is the part the character-sim research did not cover, because it only
modeled autonomous wandering. Follow and hug introduce inter-character
relationships and a stationary state.

Two orthogonal axes per character:

1. **Behavior mode** — what the character is doing:
   - `WANDER` — autonomous steering (wander + light separation + wall bounce)
   - `GROUPED` — standing still as part of a cluster (follow target)
   - `EMOTING` — transient; playing a one-shot clip (hug), then reverts to the
     previous mode

2. **Animation clip** — what is drawn: `idle`, `walk`, `hug`. Derived from the
   mode and velocity (walk when moving in WANDER or en route to a cluster slot;
   idle when stationary; hug during EMOTING).

Mode transitions:

```
spawn                      -> WANDER
!follow @target            -> join target's group -> walk to slot -> GROUPED (idle)
!leave / !join (re-issued) -> WANDER
!hug @target               -> EMOTING (play hug once) -> revert to prior mode
idle timeout               -> despawn
```

### Grouping (follow)

A group is a set of usernames standing together. Model:

- Each `Character` has `group_id: int | None`.
- A `World`-level registry: `groups: dict[int, set[str]]`.
- `A !follow B`: if B already has a group, A joins it; otherwise create a new
  group `{A, B}`. B is the anchor and does not move; A (and any later joiners)
  arrange around B in a horizontal row of standing slots, walk to their slot,
  then go idle.
- Leaving (`!leave`, re-`!join`, or despawn): remove from the group. If the
  group drops to a single member, dissolve it and that member returns to WANDER.

This gives emergent clumps of friends standing together, and multi-follow
"just works" (the cluster grows).

### Hug

`!hug @target` plays a one-shot hug clip on both characters in place, ~1.2s,
then both revert to their prior mode. With placeholder art the "hug clip" is a
simple procedural animation (e.g. a scale/bounce pulse); swapping in real LC hug
frames later is free thanks to the asset seam.

---

## Asset abstraction (the key architectural seam)

Because real LC sprites are not extracted yet, the single most important design
decision is to make the rest of the codebase blind to where art comes from.

```python
@dataclass
class SpriteSet:
    """Animation frames for one character type, keyed by clip name."""
    frames: dict[str, list[pygame.Surface]]  # "idle" | "walk" | "hug" -> frames

class AssetProvider(Protocol):
    def get_sprite_set(self, character_id: str) -> SpriteSet: ...

class PlaceholderProvider:    # v0: procedural colored shapes
    ...

class DragonBonesProvider:    # later: load exported frame folders per the
    ...                       # lc-sprites research brief
```

Sim and render code only ever see `SpriteSet`. Swapping `PlaceholderProvider`
for `DragonBonesProvider` swaps the art with zero changes elsewhere. The LC
asset-extraction work (AssetStudio -> DragonBones `_ske`/`_tex` -> exported
frames) proceeds as an independent track and lands behind this interface.

Note: placeholder sprite surfaces must be created AFTER `pygame.display.set_mode`,
because `convert_alpha()` needs an initialized display.

---

## Nameplates

Render each username to a Surface once at spawn (cache it on the character);
re-render only if the name changes (it won't). Blit it above the character's
rect each frame. Small font with a subtle outline/shadow for legibility against
the backdrop. Use a bundled TTF or `pygame.font.SysFont` for v0.

---

## Project structure (v0)

```
twitch_playground/
  main.py            # init, game loop, clock, queue drain, despawn tick
  settings.py        # flat module-level constants
  chat/
    commands.py      # ChatCommand dataclass, parse_command()
    bot.py           # twitchio client, daemon thread, puts ChatCommand on queue
  sim/
    character.py     # Character: pos, velocity, mode, anim state, nameplate
    world.py         # characters dict, groups, spawn/despawn, command handlers
    steering.py      # wander + separation + wall bounce
  render/
    scene.py         # background, y-sort draw pass, nameplate blit
  assets/
    provider.py      # SpriteSet, AssetProvider, PlaceholderProvider
  pyproject.toml
  .env.example       # TWITCH_TOKEN, TWITCH_CHANNEL
```

Design rules carried from the research: `main.py` owns the clock and event loop;
`chat/` knows nothing about rendering (only puts `ChatCommand` on the queue);
characters are looked up by username in a main-thread-only dict (no locks).

---

## Defaulted constants (override freely)

| Constant | Default |
|---|---|
| Window size | 960 x 540 |
| FPS | 12 (delta-time movement; clips authored around 12 fps) |
| Idle despawn timeout | 300 s (5 min), scanned every ~30 s |
| Hug clip duration | ~1.2 s |
| Group arrangement | horizontal row, anchored on the followed member |
| Background | flat color / simple gradient for v0 (LC facility art is a later asset) |

---

## Explicitly deferred (NOT in v0)

- Real LC DragonBones asset extraction + `DragonBonesProvider`
- Dirty-rect / `LayeredDirty` rendering (only if profiling shows full-blit isn't enough)
- Spatial grid for separation neighbor lookup (only needed past ~100 characters)
- Character / skin selection (`!character <name>`)
- Chroma-key / transparent-overlay compositing mode
- Persistence of characters across stream sessions (v0 is in-memory only)
- Additional emotes beyond hug

---

## Risks / things that will bite if ignored

1. **twitchio 2.x vs 3.x.** The research briefs assume the 2.x API
   (`twitchio.Client`, `bot.run()`, `event_message(msg)`, a simple `oauth:` chat
   token). twitchio's later major version reworked the API and auth model
   (app client id/secret, EventSub-oriented). A bare `pip install twitchio`
   pulls the latest. **Pin `twitchio>=2.10,<3` for v0** so the simple token flow
   in the research works as written. Verify the installed major version before
   building the bot. (Flagged with uncertainty — confirm the exact 3.x semantics
   when we get there.)

2. **Token expiry.** Chat oauth tokens (e.g. from twitchtokengenerator.com)
   expire. Fine for a playground; regenerate manually. Add refresh rotation only
   if this becomes a long-lived bot.

3. **macOS screen-recording permission.** Streamlabs needs the OS screen-recording
   permission to capture the pygame window on macOS. OS-level, not our code, but
   it will silently show a black capture until granted.

4. **convert_alpha ordering.** Any surface conversion (placeholder generation,
   atlas loading) must happen after `pygame.display.set_mode`.
