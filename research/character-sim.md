# Character Simulation Research
## Pygame — Movement, Animation, Spawning, State Management

---

## 1. Autonomous Movement

### Random Walk

The simplest baseline: each character picks a random direction, moves for N frames, then picks again. Works fine for ambient wandering but produces jittery, unrealistic motion.

```
velocity = random unit vector * speed
move for 60–120 frames, then re-roll
```

Better: smooth the direction change with linear interpolation (lerp) toward the new target direction over a few frames.

### Steering Behaviors (Craig Reynolds)

For more life-like wandering without a path system, two steering behaviors cover most of the need:

**Wander**
Project a circle a fixed distance ahead of the character. Each frame, nudge a point on that circle's edge by a small random angle. Steer toward that point. Result: smooth curves with gradual direction drift.

```python
wander_angle += random.uniform(-wander_jitter, wander_jitter)
wander_target = pos + heading * wander_distance + angle_to_vec(wander_angle) * wander_radius
steer = normalize(wander_target - pos) * max_speed - velocity
```

**Separation**
For each character, sum a repulsion vector from any neighbor within a separation radius. The closer the neighbor, the stronger the repulsion (inverse distance weighting). Add this to the steering force.

```python
separation = vec2(0, 0)
for neighbor in nearby:
    diff = pos - neighbor.pos
    dist = diff.length()
    if 0 < dist < sep_radius:
        separation += diff.normalize() / dist
velocity += separation * sep_weight
velocity = clamp_magnitude(velocity, max_speed)
```

A grid spatial index (see section 4) makes the neighbor lookup O(1) per character rather than O(n^2).

**Wall avoidance**
Cast a short ray in the heading direction. If it hits the window boundary within a threshold distance, add a perpendicular steering force away from the wall. Simple and convincing enough for a bounded window.

### Recommended defaults

- `max_speed`: 1.5–2.5 px/frame for a calm wandering feel
- `separation_radius`: 40–60 px (roughly 1.5x sprite width)
- `wander_jitter`: 15–25 degrees per frame
- `wander_distance`: 60 px, `wander_radius`: 25 px

---

## 2. Animation State Machine

### States

Three states cover the scope of this project:

```
IDLE -> WALK (velocity above threshold)
WALK -> IDLE (velocity below threshold)
IDLE/WALK -> INTERACT (on command event)
INTERACT -> IDLE (after interact duration expires)
```

### Per-character state machine

Keep state logic inside the character class, not in a global manager. Each character owns:
- `state: str` — current state name
- `frame_index: float` — accumulates via `frame_index += anim_speed * dt`
- `frame_count: int` — frames in the current state's strip

```python
class AnimStateMachine:
    ANIM_ROWS = {"idle": 0, "walk": 1, "interact": 2}

    def update(self, velocity, dt):
        speed = velocity.length()
        if self.state == "interact":
            self.frame_index += self.anim_speed * dt
            if self.frame_index >= self.frame_count["interact"]:
                self.transition("idle")
        elif speed > WALK_THRESHOLD:
            if self.state != "walk":
                self.transition("walk")
            self.frame_index += self.anim_speed * dt
        else:
            if self.state != "idle":
                self.transition("idle")
            self.frame_index += self.idle_anim_speed * dt

        self.frame_index %= self.frame_count[self.state]

    def transition(self, new_state):
        self.state = new_state
        self.frame_index = 0.0

    @property
    def current_frame(self):
        row = self.ANIM_ROWS[self.state]
        col = int(self.frame_index)
        return self.sheet.subsurface((col * W, row * H, W, H))
```

### Driving frame index from state

Use float accumulation (`frame_index: float`) rather than integer frame counting. This lets you decouple animation speed from framerate. Multiply by `dt` (seconds since last frame) for frame-rate independence.

---

## 3. Performance for 50–200 Characters

### Sprite group strategy

Use `pygame.sprite.LayeredUpdates` (handles draw order) with `pygame.sprite.Group.draw()` and dirty rect tracking via `pygame.sprite.RenderUpdates` or `pygame.sprite.DirtySprite`.

For 200 characters at 60 fps, the bottleneck is almost always surface blitting, not Python logic. Keep per-frame Python work O(n) and avoid any O(n^2) neighbor search.

### Dirty rect rendering

Instead of `display.flip()`, use `display.update(dirty_rects)`. Each sprite that moved marks its old rect dirty. The renderer only redraws those regions. Massive win on a mostly-static background.

```python
dirty = group.draw(screen)  # RenderUpdates.draw() returns dirty rects
pygame.display.update(dirty)
```

This only helps if the background is pre-rendered to a surface and blitted once. Dynamic backgrounds negate the benefit.

### Spatial grid for neighbor lookup

Divide the window into cells of `cell_size = sep_radius`. Each frame, rebuild a dict mapping `(cx, cy) -> [character, ...]`. To find neighbors of character C, check the 9 cells around C's cell. Rebuild cost is O(n); lookup per character is O(1) amortized.

```python
grid = defaultdict(list)
for char in characters:
    cx, cy = int(char.x // cell_size), int(char.y // cell_size)
    grid[(cx, cy)].append(char)

def neighbors(char):
    cx, cy = int(char.x // cell_size), int(char.y // cell_size)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            yield from grid[(cx + dx, cy + dy)]
```

At 200 characters a quadtree is overkill; the grid is simpler and faster to rebuild every frame.

### Avoid per-frame surface creation

Pre-slice all animation frames from the spritesheet at load time into a 2D list `frames[state][col]`. In `update()`, just index into this list — no `subsurface()` calls per frame.

```python
# at load time
frames = {}
for state, row in ANIM_ROWS.items():
    frames[state] = [
        sheet.subsurface((col * W, row * H, W, H))
        for col in range(frame_counts[state])
    ]
```

---

## 4. Sprite Layering / Composite Characters

Lobotomy Corporation characters are built from layered parts (body, head, equipment, etc.). Two approaches:

### Option A: Composite at load time (recommended for this project)

For each character variant, blit all layer surfaces onto a single surface once when the character is created. Store the composited surface. Per-frame: just blit that one surface. Zero per-frame overhead.

```python
def build_composite(layers: list[Surface], size) -> Surface:
    composite = Surface(size, pygame.SRCALPHA)
    for layer in layers:
        composite.blit(layer, (0, 0))
    return composite
```

Works well when layers don't animate independently. For this project (idle/walk/interact) where the whole sprite animates together, this is the right call.

### Option B: Blit layers separately per frame

Blit each layer surface at the character's position each frame. More flexible (layers can animate at different rates), but adds n_layers * n_characters blits per frame. At 200 characters with 4 layers each, that is 800 blits vs 200 — noticeable.

Use Option B only if layers need independent animation (e.g., a floating hat that bobs separately from the walk cycle).

### Z-ordering

`LayeredUpdates.change_layer(sprite, layer)` handles draw order. Assign layer based on y-position (higher y = drawn later = in front). Recalculate each frame:

```python
for char in characters.values():
    group.change_layer(char, int(char.rect.centery))
```

---

## 5. Thread-safe Spawning from Twitch Background Thread

The Twitch IRC client runs in a background thread. Pygame's event system and surface operations are not thread-safe. The canonical pattern is a thread-safe queue:

```python
import queue
spawn_queue: queue.Queue = queue.Queue()

# In Twitch IRC thread (on !spawn command):
spawn_queue.put({"type": "spawn", "username": username})
spawn_queue.put({"type": "interact", "username": username, "action": "pet"})

# In main game loop (each frame):
while not spawn_queue.empty():
    event = spawn_queue.get_nowait()
    if event["type"] == "spawn":
        handle_spawn(event["username"])
    elif event["type"] == "interact":
        handle_interact(event["username"], event["action"])
```

Never call any pygame surface or group operation from the Twitch thread. All pygame work happens on the main thread, draining the queue at the top of each game loop iteration.

Alternatively, push to `pygame.event.post()` using a custom event type — the main event loop already processes events each frame, so this integrates cleanly:

```python
TWITCH_EVENT = pygame.event.custom_type()  # pygame 2.x

# from Twitch thread:
pygame.event.post(pygame.event.Event(TWITCH_EVENT, {"username": u, "cmd": "spawn"}))

# in main loop:
for event in pygame.event.get():
    if event.type == TWITCH_EVENT:
        handle_twitch(event)
```

`pygame.event.post()` is documented as thread-safe. The queue approach is more explicit and easier to test outside pygame; `event.post` integrates with the existing event dispatch. Either works — pick one and be consistent.

---

## 6. Per-user State: username -> Character Instance

```python
characters: dict[str, Character] = {}

def handle_spawn(username: str):
    if username in characters:
        # already exists — reset idle timer instead
        characters[username].reset_idle_timer()
        return
    char = Character(username=username, pos=random_spawn_pos())
    characters[username] = char
    group.add(char)

def handle_interact(username: str, action: str):
    if username not in characters:
        handle_spawn(username)  # auto-spawn on first interaction
    characters[username].trigger_interact(action)
```

The dict is only accessed from the main thread (all mutations happen when draining the queue), so no lock is needed.

---

## 7. Despawning / Idle Timeout

Each character tracks `last_interaction_time` (monotonic clock). Each frame (or on a lower-frequency tick — every 30 seconds), scan for characters past the timeout:

```python
IDLE_TIMEOUT_SECONDS = 300  # 5 minutes

def tick_despawn(characters: dict, group: Group, now: float):
    to_remove = [
        username
        for username, char in characters.items()
        if now - char.last_interaction_time > IDLE_TIMEOUT_SECONDS
    ]
    for username in to_remove:
        char = characters.pop(username)
        char.kill()  # removes from all sprite groups
```

Call `tick_despawn` every N frames rather than every frame to avoid scanning the entire dict 60x/second:

```python
if frame_count % 1800 == 0:  # every 30 seconds at 60 fps
    tick_despawn(characters, group, time.monotonic())
```

Characters can play a "fade out" animation before `kill()` by adding a `despawning: bool` state and a countdown.

---

## Character Class Sketch

```python
import pygame
import time
import math
import random
from pygame.math import Vector2

WALK_THRESHOLD = 0.3  # px/frame below which character is "idle"
IDLE_TIMEOUT = 300.0  # seconds

class Character(pygame.sprite.DirtySprite):
    def __init__(self, username: str, pos: tuple, frames: dict, cell_size: int = 48):
        super().__init__()
        self.username = username
        self.pos = Vector2(pos)
        self.velocity = Vector2(0, 0)
        self.frames = frames  # {"idle": [...], "walk": [...], "interact": [...]}

        # steering
        self.wander_angle = random.uniform(0, 360)
        self.max_speed = 2.0

        # animation
        self.state = "idle"
        self.frame_index = 0.0
        self.anim_speed = 8.0  # frames per second

        # lifecycle
        self.last_interaction_time = time.monotonic()
        self.interact_timer = 0.0

        self.image = self.frames["idle"][0]
        self.rect = self.image.get_rect(center=map(int, self.pos))
        self.dirty = 1

    def trigger_interact(self, action: str = "interact"):
        self.state = "interact"
        self.frame_index = 0.0
        self.interact_timer = len(self.frames["interact"]) / self.anim_speed
        self.last_interaction_time = time.monotonic()

    def reset_idle_timer(self):
        self.last_interaction_time = time.monotonic()

    def apply_separation(self, neighbors):
        sep = Vector2(0, 0)
        for n in neighbors:
            if n is self:
                continue
            diff = self.pos - n.pos
            dist = diff.length()
            if 0 < dist < 50:
                sep += diff.normalize() / dist
        self.velocity += sep * 1.5

    def update(self, dt: float, neighbors):
        if self.state == "interact":
            self.interact_timer -= dt
            if self.interact_timer <= 0:
                self.state = "idle"
                self.frame_index = 0.0
        else:
            # wander steering
            self.wander_angle += random.uniform(-20, 20)
            rad = math.radians(self.wander_angle)
            wander_vec = Vector2(math.cos(rad), math.sin(rad)) * 25
            heading = self.velocity.normalize() if self.velocity.length() > 0.01 else Vector2(1, 0)
            target = self.pos + heading * 60 + wander_vec
            steer = (target - self.pos).normalize() * self.max_speed - self.velocity

            self.velocity += steer * 0.05
            self.apply_separation(neighbors)
            if self.velocity.length() > self.max_speed:
                self.velocity.scale_to_length(self.max_speed)

            self.pos += self.velocity

            # wall bounce
            screen_w, screen_h = pygame.display.get_surface().get_size()
            margin = 30
            if self.pos.x < margin:
                self.velocity.x = abs(self.velocity.x)
            elif self.pos.x > screen_w - margin:
                self.velocity.x = -abs(self.velocity.x)
            if self.pos.y < margin:
                self.velocity.y = abs(self.velocity.y)
            elif self.pos.y > screen_h - margin:
                self.velocity.y = -abs(self.velocity.y)

            # state transition
            new_state = "walk" if self.velocity.length() > WALK_THRESHOLD else "idle"
            if new_state != self.state:
                self.state = new_state
                self.frame_index = 0.0

        # advance animation
        frame_count = len(self.frames[self.state])
        self.frame_index = (self.frame_index + self.anim_speed * dt) % frame_count
        new_image = self.frames[self.state][int(self.frame_index)]
        if new_image is not self.image:
            self.image = new_image
            self.dirty = 1

        old_center = self.rect.center
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.rect.center != old_center:
            self.dirty = 1
```

---

## Recommended Architecture Summary

| Concern | Recommendation |
|---|---|
| Movement | Wander steering + separation, wall bounce |
| Animation | Float-accumulation state machine, pre-sliced frames dict |
| Performance | DirtySprite + RenderUpdates, spatial grid, pre-composited layers |
| Layering | Composite at load time; z-order by y each frame via LayeredUpdates |
| Spawn from thread | Thread-safe queue drained at top of game loop |
| User state | `dict[str, Character]`, main-thread only |
| Despawn | Idle timeout scan every 30 s, `char.kill()` removes from groups |

The above design handles 50–200 characters at 60 fps on a modern machine without needing numpy or C extensions. If profiling shows the Python steering loop is the bottleneck past 200 characters, the natural next step is batching position updates with numpy arrays — but that is premature until measured.
