# T-001: Low-CPU/GPU pygame rendering for many sprites

Research brief for the Lobotomy Corporation Twitch character playground.
Goal: display many animated sprites simultaneously with minimal CPU and GPU burn.

---

## 1. Dirty rect updating vs full-surface blit

**Full blit** redraws the entire screen every frame — simple, works for any scene, but
wastes CPU on pixels that didn't change. At 60 fps on a 1920x1080 surface this is
~500 MB/s of memory bandwidth even when nothing moves.

**Dirty rect updating** tracks which screen regions changed and calls
`pygame.display.update(dirty_rects)` with only those rectangles. The OS composites
only the dirty tiles, slashing bandwidth by 80-95% when the scene is mostly static.

**Recommendation for this project:** use dirty rects. Twitch characters stand around,
emote occasionally, and the background is static. Most frames only a handful of sprites
will actually be animating.

The manual dirty rect pattern:

```python
dirty = []
for sprite in all_sprites:
    old_rect = sprite.rect.copy()
    sprite.update()  # mutates sprite.rect / image if animating
    if sprite.dirty:
        screen.blit(background, old_rect, old_rect)  # erase old position
        screen.blit(sprite.image, sprite.rect)
        dirty.append(old_rect.union(sprite.rect))
pygame.display.update(dirty)
```

---

## 2. `LayeredDirty` and `DirtySprite`

pygame ships a purpose-built group for this: `pygame.sprite.LayeredDirty`. It manages
the dirty-rect pipeline automatically and handles layering (z-order) natively.

`DirtySprite` adds two key attributes:
- `dirty` — 0 = clean, 1 = redraw once, 2 = always redraw (for animated sprites)
- `visible` — toggle without removing from group

Usage:

```python
import pygame
from pygame.sprite import DirtySprite, LayeredDirty

class Character(DirtySprite):
    def __init__(self, sheet, layer=0):
        super().__init__()
        self.frames = sheet          # list of surfaces from atlas
        self.frame_idx = 0
        self.image = self.frames[0]
        self.rect = self.image.get_rect()
        self._layer = layer
        self.dirty = 1               # draw once on spawn

    def animate(self):
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        self.image = self.frames[self.frame_idx]
        self.dirty = 1               # signal redraw for this frame

group = LayeredDirty(background=background_surface)

# Each frame:
dirty_rects = group.draw(screen)
pygame.display.update(dirty_rects)
```

`LayeredDirty` erases sprites at their old positions automatically using the background
surface you pass. Set `sprite.dirty = 2` for continuously animating sprites, `1` for
one-shot updates, `0` when idle.

**This is the recommended rendering primitive for this project.**

---

## 3. Hardware-accelerated surfaces: HWSURFACE / DOUBLEBUF / OPENGL

| Flag | What it does | Verdict for this project |
|---|---|---|
| `HWSURFACE` | Attempts to place the display surface in video RAM | Rarely beneficial on modern OS with compositing; often falls back silently |
| `DOUBLEBUF` | Double-buffering, eliminates tearing | Use with `HWSURFACE`; negligible overhead |
| `OPENGL` | Full OpenGL context — pygame blitting APIs no longer work | Only if switching to a GL-native renderer (e.g. ModernGL) |
| `SCALED` | pygame scales a fixed-res surface to the window | Useful for pixel-art; one extra blit per frame |
| (none) | Software surface | Reliable, predictable, works everywhere |

**Recommendation:** `pygame.DOUBLEBUF` is essentially free and eliminates screen tear.
`HWSURFACE` is a hint the driver usually ignores on modern desktops. Skip OpenGL unless
you need shader effects — it requires abandoning the pygame sprite API entirely.

```python
screen = pygame.display.set_mode((1280, 720), pygame.DOUBLEBUF)
```

If you later need GPU compositing for effects (glow, transparency blending), consider
`pygame-ce` (community edition) which has better hardware surface support, or move the
rendering layer to `moderngl` with a thin pygame window.

---

## 4. Sprite batching and atlas textures

**The core problem:** each `surface.blit()` call has overhead. Many small blits to
separate surfaces are slower than one blit from a large atlas.

**Atlas textures:** pack all animation frames into a single large surface at load time.
Blitting a subrect of one surface is much cheaper than blitting many individual surfaces.

```python
def load_atlas(path, frame_w, frame_h):
    sheet = pygame.image.load(path).convert_alpha()
    cols = sheet.get_width() // frame_w
    rows = sheet.get_height() // frame_h
    frames = []
    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
            frame = sheet.subsurface(rect)  # zero-copy view into atlas
            frames.append(frame)
    return frames
```

`subsurface()` returns a view — no pixel copy — so the atlas stays in memory once and
each frame reference is cheap.

**Batch blitting:** `pygame.Surface.blits(blit_list)` accepts a list of
`(surface, dest)` tuples and executes them in a tight C loop, bypassing Python per-call
overhead. For N sprites this can be 3-5x faster than a Python loop of individual blits.

```python
blit_list = [(sprite.image, sprite.rect) for sprite in visible_sprites]
screen.blits(blit_list)
```

**Recommendation:** use atlas textures loaded via `subsurface()` for all character
animations, and prefer `screen.blits()` if you bypass `LayeredDirty` for any batch draw.

---

## 5. Clock and frame-rate limiting

Without rate limiting the render loop runs as fast as the CPU allows, pinning a core
at 100% for no visual benefit.

```python
clock = pygame.time.Clock()

while running:
    dt = clock.tick(60)  # sleep until next 60fps slot; returns ms elapsed
    # or:
    dt = clock.tick_busy_loop(60)  # spin-waits — lower jitter, higher CPU
```

`clock.tick()` calls `pygame.time.delay()` internally, which yields to the OS scheduler.
On most systems this keeps CPU usage under 5% when nothing is animating.

**Frame-rate strategy:**
- Target 30 fps if the scene is mostly idle characters — halves CPU cost vs 60 fps.
- Use delta-time (`dt / 1000.0`) for all movement so behavior is rate-independent.
- Separate animation tick rate from render tick rate: advance sprite frames every
  N ms regardless of render fps.

```python
ANIM_INTERVAL = 100  # ms per animation frame
anim_accumulator = 0

while running:
    dt = clock.tick(30)
    anim_accumulator += dt
    if anim_accumulator >= ANIM_INTERVAL:
        anim_accumulator -= ANIM_INTERVAL
        for sprite in animating_sprites:
            sprite.advance_frame()  # sets dirty=1
```

---

## 6. Threading model: Twitch IRC + render loop

pygame's display and event system must run on the main thread (SDL2 requirement).
Twitch IRC is I/O-bound — blocking reads would stall the render loop.

**Recommended model: IRC on a daemon thread, render on main thread, communicate via
`queue.Queue`.**

```python
import threading
import queue

chat_queue = queue.Queue()

def irc_thread(q):
    # connect, authenticate, loop
    for message in irc_connection:
        q.put(message)         # non-blocking put; render loop drains this

t = threading.Thread(target=irc_thread, args=(chat_queue,), daemon=True)
t.start()

# In the render loop:
while running:
    while not chat_queue.empty():
        msg = chat_queue.get_nowait()
        handle_chat_message(msg)   # spawn character, trigger emote, etc.

    # ... render ...
    clock.tick(30)
```

`queue.Queue` is thread-safe. The render loop drains the queue at the start of each
frame — no locking needed in user code.

**Avoid:** `pygame.event.post()` for IRC events — it works but adds unnecessary
complexity and the event queue has a default cap of 32 events.

**Alternative:** `asyncio` for the IRC layer (using `irc3` or `twitchio`) with
`asyncio.run_coroutine_threadsafe()` to bridge into a thread. This scales better if
you later need multiple IRC connections or HTTP calls, but is more setup.

---

## 7. pygame alternatives

| Library | Rendering model | Pros | Cons |
|---|---|---|---|
| **pygame-ce** | Same as pygame, SDL2 | Drop-in fork; better hardware surface support, active maintenance, `blits()` is faster | Minor API deltas vs upstream pygame |
| **pyglet** | OpenGL via pyglet.graphics | Built-in sprite batching, GPU compositing, easy shader access | Different API; no "sprite group" analog; steeper curve |
| **arcade** | OpenGL (pyglet under the hood) | High-level sprite API, sprite lists are GPU batches, easy physics | Heavier dependency; 2D game engine feel vs toolkit feel |
| **pygame + moderngl** | pygame window + OpenGL context | Full GPU control, shaders, instanced rendering for 1000+ sprites | Significant boilerplate; blending pygame surfaces into GL requires texture upload |

**Recommendation for this project:** start with **pygame-ce** (community edition).
It's a drop-in upgrade from pygame with better performance, still ships `LayeredDirty`,
and doesn't require rewriting any rendering code. Install:

```
pip install pygame-ce
```

If you later need to render 500+ simultaneous characters with glow/shader effects,
**arcade** is the cleanest high-level upgrade path — its `SpriteList` maps directly to
a GPU-instanced draw call.

---

## 8. Recommended project structure

```
project/
    main.py                  # entry point: init, game loop, clock
    settings.py              # SCREEN_W, SCREEN_H, FPS, TARGET_LAYER, etc.

    rendering/
        __init__.py
        group.py             # LayeredDirty group setup, draw() wrapper
        atlas.py             # load_atlas(), subsurface slicing

    characters/
        __init__.py
        base.py              # Character(DirtySprite): load frames, animate()
        registry.py          # name -> Character class lookup for chat spawning

    chat/
        __init__.py
        irc.py               # IRC thread, auth, message parsing
        events.py            # ChatMessage dataclass; queue bridge

    assets/
        sprites/             # sprite sheets per character
        backgrounds/

    tests/
        test_atlas.py
        test_character.py
```

Key design rules:
- `main.py` owns the clock and the event loop. Nothing else calls `clock.tick()`.
- `chat/irc.py` knows nothing about rendering — it only puts `ChatMessage` objects
  onto the shared queue.
- `characters/` sprites are registered by name so a chat `!spawn korveil` maps to a
  class lookup, not a hardcoded branch.
- Keep `settings.py` flat — no class, just module-level constants. Easy to override
  in tests.

---

## Summary recommendations

| Concern | Decision |
|---|---|
| Render strategy | `LayeredDirty` + dirty-rect update |
| Surface flags | `pygame.DOUBLEBUF` only |
| Texture loading | Atlas sheets via `subsurface()` |
| Batch draw | `screen.blits()` for manual batches |
| Frame rate | 30 fps + delta-time animation ticks |
| IRC integration | Daemon thread + `queue.Queue` |
| Library | `pygame-ce` (drop-in, better perf) |
| Upgrade path | `arcade` if >500 sprites or shaders needed |
