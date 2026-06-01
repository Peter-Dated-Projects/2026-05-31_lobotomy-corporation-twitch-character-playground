# Lobotomy Corporation: Sprite & Character Component System

## Overview

Lobotomy Corporation (Project Moon, 2018) renders characters by compositing multiple independent
sprite layers at runtime. Each character — both Abnormalities and employees/agents — is not a
single flat sprite but a stack of PNG layers that are drawn in a fixed Z-order each frame. This
lets the game swap equipment, express emotional state changes, and run per-body-part animations
without duplicating the full character art for every combination.

---

## Layer Anatomy

### Employee (Agent) Characters

Employees use the most layered setup because they have swappable equipment:

| Layer (bottom to top) | Contents |
|---|---|
| Shadow | Soft drop shadow under the feet |
| Body | Torso, legs, base clothing |
| Back equipment | Weapons or tools worn on the back |
| Head | Head shape, hair |
| Face | Eyes, mouth — expression sprites |
| Front arm | The arm facing the camera |
| Front-arm equipment | Weapon held in the front hand |
| Back arm | The arm behind the body |
| Back-arm equipment | Off-hand weapon or shield |
| Costume overlay | Sephirah uniform, special suit pieces |
| UI/name tag | Not a sprite layer — drawn by the HUD system |

Exact layer ordering was confirmed by community sprite rippers who extracted the asset bundles;
the back-to-front order above matches what modders observed when manually compositing the sheets.

### Abnormality Characters

Abnormalities vary widely in complexity. Simple ones are a single animated sheet; complex ones
(e.g., multi-part bosses, transforming creatures) use 4-8 layers. Common split points:

- **Base body** — main silhouette
- **Appendages** — tentacles, wings, extra limbs (each may be its own layer with its own
  animation cycle, so they can flap or writhe independently of the body idle)
- **Face / eyes** — expression overlays, blinking, pupil tracking
- **Glow / effect layer** — particle-like static overlays (e.g. aura sprites drawn additively)
- **Attack effect** — a separate sprite sheet that appears only during the attack animation

---

## Skeleton / Rig vs Frame-by-Frame

LC uses **DragonBones** (the Egret/Dragonbones runtime, a Chinese open-source 2D skeletal
animation tool comparable to Spine2D). Evidence:

- The Unity AssetBundle extracts produce `.json` + texture-atlas PNG pairs in the DragonBones
  format: a `_ske.json` describing bones/slots/animations and a `_tex.json` texture atlas
  manifest paired with `_tex.png`.
- Community tools (notably `LCSprite` and various AssetStudio exports) expose this structure
  directly: each character folder contains `<name>_ske.json` + `<name>_tex.json` + `<name>_tex.png`.
- The DragonBones runtime drives bones at runtime; individual frames are not pre-baked — the
  game evaluates the skeleton pose each frame and blits only the required atlas regions.

This means the animation data is **keyframe-interpolated skeletal**, not frame-by-frame
flipbook. However, for a fan pygame project the practical difference is small: the community
has pre-exported the animations as frame sequences (see "Community Tools" below), so you can
treat them as flipbooks.

---

## File Formats

| Asset | Format | Notes |
|---|---|---|
| Texture atlas | PNG | Power-of-two dimensions; multiple sprites packed into one sheet |
| Atlas manifest | JSON (DragonBones `_tex.json`) | Maps sprite name -> rect (x, y, w, h) within the PNG |
| Skeleton/animation data | JSON (DragonBones `_ske.json`) | Bone hierarchy, slot bindings, animation keyframes |
| Unity bundle | `.assets` / AssetBundle | Raw container; must be unpacked with AssetStudio or similar |

The Google Drive folder at
`https://drive.google.com/drive/folders/1WiahaZ5hBY5YZp_CFserxYf_-q65jTYZ`
likely contains assets already extracted from the bundles — expect the directory structure to
mirror the in-game character IDs, with each character having a subfolder containing the `_ske`
+ `_tex` pair or pre-rendered frame PNGs.

---

## Runtime Layer Composition

At runtime (Unity/C#), LC:

1. Instantiates a `DragonBones.UnityArmatureComponent` per character.
2. Each layer/slot in the DragonBones armature can display a different texture region; swapping
   equipment means updating the slot's `DisplayIndex` or replacing the `DisplayData` texture to
   point at the equipment skin's atlas region.
3. Z-order is encoded in the DragonBones slot order; Unity renders them as separate
   `SpriteRenderer` components with ascending `sortingOrder` values.
4. Skin sets group the texture replacements for a full equipment loadout — equipping a weapon
   changes the "front-arm-equip" slot's skin, not the skeleton itself.

### State Transitions

The armature plays named animation clips (e.g. `"idle"`, `"walk"`, `"attack_0"`, `"die"`).
The game code calls `armature.animation.Play("attack_0")` and the DragonBones runtime handles
the keyframe interpolation. Layers that are not active in a particular state are simply hidden
(their slot alpha set to 0 or their display cleared).

---

## Community Reverse-Engineering and Tools

| Tool / Resource | What it does |
|---|---|
| **AssetStudio** | Extracts Unity AssetBundles; can export textures, mesh, and MonoBehaviour JSON |
| **UABE (Unity Assets Bundle Extractor)** | Alternative extractor; good for batch PNG export |
| **LCSprite (GitHub)** | Fan tool specifically for LC; parses `_ske.json` + `_tex.json` and renders frame sequences |
| **DragonBones Viewer (official)** | Loads `_ske` + `_tex` pairs natively for visual inspection |
| **LC Mod Discord** | Active community with sprite rip guides; search "texture atlas" in their pins |
| **LC Wiki sprite dumps** | Some wikis host pre-cut PNGs of individual sprites (heads, bodies) for quick reference |

The most common fan-project approach: extract via AssetStudio, load the atlas PNG + JSON with a
DragonBones Python port or your own atlas parser, then render the required frames.

---

## Animation States Per Layer

DragonBones allows each layer/slot to have its own independent timeline. In LC:

| State | Typical behavior |
|---|---|
| `idle` | Gentle breathing bob on the body; eyes blink on the face layer; hair/appendages have a slight sway on a longer cycle |
| `move` / `walk` | Leg cycle on body layer; arm swing; head stays relatively stable |
| `attack` | Full-body forward lunge; attack-effect layer fades in, plays, fades out; expression changes to "exert" |
| `skill` (Abnormalities) | Custom per-Abnormality; often a separate animation clip that resets to idle |
| `panic` / `hit` | Short interrupt clip; blends back to idle |
| `die` | Non-looping clip; character fades or ragdolls |

Independent layer cycles are achieved by having each slot's animation timeline loop on its own
duration (e.g. the blink cycle is 3 s, the breathing bob is 2 s — they run in parallel on the
same armature).

---

## Practical Pygame Replication

### Architecture

```
Character
  |-- list of Layer objects (ordered back-to-front)
        |-- current_frame_index
        |-- frames: list of pygame.Surface  (pre-sliced from atlas)
        |-- frame_duration_ms
        |-- loop: bool
        |-- state: str  ("idle", "walk", "attack", ...)
```

### Step-by-Step

**1. Parse the atlas**

```python
import json
from pathlib import Path
import pygame

def load_atlas(tex_json: Path, tex_png: Path) -> dict[str, pygame.Surface]:
    sheet = pygame.image.load(tex_png).convert_alpha()
    manifest = json.loads(tex_json.read_text())
    sprites = {}
    for entry in manifest["SubTexture"]:
        x, y, w, h = entry["x"], entry["y"], entry["width"], entry["height"]
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), (x, y, w, h))
        sprites[entry["name"]] = surf
    return sprites
```

**2. Build frame sequences per animation state**

The `_ske.json` lists animation clips with frame-by-frame slot display data. For a simpler
approach, pre-export frames with LCSprite (or AssetStudio's sprite sequence export), then load
them as a numbered sequence:

```python
def load_frame_sequence(folder: Path, state: str) -> list[pygame.Surface]:
    frames = sorted(folder.glob(f"{state}_*.png"))
    return [pygame.image.load(f).convert_alpha() for f in frames]
```

**3. Layer class**

```python
class Layer:
    def __init__(self, frames: list[pygame.Surface], fps: int = 12, loop: bool = True):
        self.frames = frames
        self.frame_ms = 1000 / fps
        self.loop = loop
        self._elapsed = 0.0
        self._idx = 0

    def update(self, dt_ms: float):
        if not self.frames:
            return
        self._elapsed += dt_ms
        while self._elapsed >= self.frame_ms:
            self._elapsed -= self.frame_ms
            self._idx += 1
            if self._idx >= len(self.frames):
                self._idx = 0 if self.loop else len(self.frames) - 1

    def surface(self) -> pygame.Surface | None:
        if not self.frames:
            return None
        return self.frames[self._idx]
```

**4. Character compositor**

```python
class Character:
    def __init__(self, layers: list[Layer]):
        self.layers = layers  # ordered back-to-front

    def update(self, dt_ms: float):
        for layer in self.layers:
            layer.update(dt_ms)

    def draw(self, screen: pygame.Surface, pos: tuple[int, int]):
        for layer in self.layers:
            surf = layer.surface()
            if surf:
                screen.blit(surf, pos)
```

**5. State switching**

When transitioning states, swap each layer's frame list:

```python
class StatefulLayer:
    def __init__(self, state_frames: dict[str, list[pygame.Surface]], fps: int = 12):
        self.state_frames = state_frames
        self.fps = fps
        self._state = "idle"
        self._layer = Layer(state_frames.get("idle", []), fps)

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        self._layer = Layer(self.state_frames.get(state, []), self.fps,
                            loop=(state == "idle" or state == "walk"))

    def update(self, dt_ms: float):
        self._layer.update(dt_ms)

    def surface(self):
        return self._layer.surface()
```

### Performance Notes

- Pre-convert all surfaces with `.convert_alpha()` at load time.
- For many simultaneous characters, use a single `pygame.sprite.LayeredUpdates` group or
  blit all layers in a single pass per character — avoid per-frame Surface construction.
- If you have 20+ characters on screen, consider blitting each character to a single cached
  Surface each frame and dirtying it only when the frame index changes (dirty-rect approach).
- Keep atlas PNGs loaded once and share the sliced Surface objects across instances of the
  same character type.

---

## Key Takeaways

1. **LC characters are DragonBones skeletal rigs**, but the community has pre-exported them as
   frame sequences, so you can treat them as flipbook animations in pygame.
2. **Each visual feature is a separate layer** — body, head, face, limbs, equipment, effects.
   Compositing is just drawing them back-to-front at the same screen position.
3. **Equipment swapping** = replacing one layer's frame set; the skeleton doesn't change.
4. **Animation states** are named clips; layers run their own cycle lengths independently.
5. **For pygame**: load atlas -> slice frames -> Layer objects per slot -> draw in Z-order each
   frame. The architecture is simple; the work is in asset extraction and frame sequencing.
