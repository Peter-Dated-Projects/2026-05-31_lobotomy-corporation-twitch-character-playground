# Sidescroller Rebuild — Shared Contract

Single source of truth for the parallel rebuild. Every ticket codes against the
interfaces below so the tracks integrate without drift. If you need to change an
interface here, that is a coordination event — update this doc.

## Vision

Side view, not top-down. Characters stroll left/right on a ground platform.
Floating platforms sit above the ground; characters reach them by jumping
(real gravity, one-way platforms — pass up through, land on top when falling).
Some characters end up hopping around on the platforms. It should read as a
lively little crowd.

## Coordinate convention

- A character's `pos` (pygame `Vector2`) is its **feet** position:
  `pos.x` = horizontal center, `pos.y` = the y of the surface it stands on.
- Sprites render with their **midbottom** anchored at `pos`.
- Smaller y = higher on screen (standard pygame).

## sim/platforms.py  (already created — extend, don't rewrite from scratch)

```python
@dataclass(frozen=True)
class Platform:
    left: float; right: float; top: float
    def contains_x(self, x) -> bool
    @property center_x -> float

def default_level() -> list[Platform]      # index 0 is the full-width ground
def landing_surface(platforms, prev_feet_y, feet_y, x) -> Platform | None
```

## settings.py additions (owned by the Sim-engine ticket)

`GROUND_TOP` (feet-y of the ground), `GRAVITY` (px/s^2), `JUMP_SPEED` (px/s up),
`WALK_SPEED` (px/s horizontal), jump/idle decision chances, and a small
horizontal-separation radius/push so characters don't fully overlap on a
platform. Tune so each platform tier is within one jump of the tier below.

## Character public API (owned by Sim-engine ticket; consumed by World + Render)

```python
class Mode(Enum): WANDER; GROUPED; EMOTING

class Character:
    def __init__(self, username, pos, sprites, nameplate)
    # attrs read by other tracks:
    pos: Vector2          # feet (x, surface_y)
    velocity: Vector2
    mode: Mode
    group_id: int | None
    group_slot: Vector2 | None
    platform: Platform | None     # surface currently standing on (None if airborne)
    clip: str                     # current animation clip name
    last_interaction: float
    # methods:
    def touch(self)
    def trigger_hug(self)
    def set_grouped(self, gid: int, slot: Vector2)   # snaps onto slot's platform, stands
    def set_wander(self)
    def update(self, dt, neighbor_positions: list[Vector2], platforms: list[Platform])
    @property surface -> pygame.Surface
```

Behavior:
- **WANDER**: stroll horizontally on the current platform; turn around at
  platform edges and screen walls; occasional idle pauses; occasional jumps
  (`vel.y = -JUMP_SPEED`). Gravity applies; landing via `landing_surface`.
- **GROUPED**: stand at `group_slot` (snapped onto its platform); no wander.
- **EMOTING**: play the `hug` clip for `settings.HUG_DURATION`, then revert to
  the previous mode. Stationary while emoting.
- **clip selection**: `"hug"` when EMOTING; `"jump"` when airborne; `"walk"`
  when moving horizontally on a surface; else `"idle"`.

## SpriteSet clips (owned by Sim-engine ticket, in assets/provider.py)

Must provide: `idle`, `walk`, `hug`, **and a new `jump`** clip (a stretched
airborne pose works for the placeholder).

## World (owned by World ticket)

- `__init__`: build `self.platforms = default_level()`.
- `spawn(username)`: place the new character on the **ground** platform at a
  random x, feet at `GROUND_TOP`.
- `update(dt)`: pass `self.platforms` into each `character.update(...)`.
- **Grouping (follow)**: a follower stands **beside the leader on the leader's
  platform** — `slot.y = leader.platform.top`, `slot.x` beside the leader,
  clamped to that platform's span. Anchor (leader) stays put; followers fan out.
- **Fix the reported bugs**: `!follow`, `!hug`, `!leave` must each be
  observably correct (see Acceptance below). Reproduce headlessly first.

## Render

- `render/scene.py` (owned by World ticket): fill background; draw `world.platforms`
  (ground as a floor band, floating platforms as slabs); draw characters
  midbottom-anchored, sorted by `pos.y`; nameplate above each.
- `render/hud.py` (owned by HUD ticket): a debug overlay drawn AFTER the scene —
  viewer count, a tiny per-character `mode/clip` label, and a rolling log of the
  last ~6 commands so effects are visible. Read observable state
  (`world.characters`, each character's `mode`/`group_id`/`clip`); do not edit
  `world.py`.

## Acceptance (what "working" means)

- `!join` spawns a character on the ground; it strolls and occasionally hops.
- `!follow @b` makes the sender walk to `b` and stand beside it on b's platform.
- `!hug @b` plays the hug clip on both, then both resume their prior behavior —
  it does NOT freeze them permanently.
- `!leave` returns the sender to wandering and dissolves a 1-member cluster.
- The HUD makes each of the above visible without guesswork.

## File ownership (no cross-track edits)

- Sim-engine: `sim/character.py`, `sim/platforms.py`, `sim/steering.py`, `settings.py`, `assets/provider.py`
- World: `sim/world.py`, `render/scene.py`
- HUD: `render/hud.py`, `dev.py`, `main.py`
- Tests: `tests/**`
