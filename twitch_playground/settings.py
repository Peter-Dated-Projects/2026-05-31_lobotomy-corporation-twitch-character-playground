"""Flat module-level configuration. Override in tests by reassigning."""

# Window / render
SCREEN_W = 960
SCREEN_H = 540
FPS = 12  # deliberate low-fps / stop-motion look; movement is delta-time based
CAPTION = "LobCorp Twitch Playground"
BG_COLOR = (24, 26, 32)
WALL_MARGIN = 36  # characters bounce / clamp inside this inset

# Sprite
SPRITE_W = 32
SPRITE_H = 40

# Movement (px/sec, since we integrate with delta-time)
MAX_SPEED = 70.0
WALK_THRESHOLD = 8.0  # speed below which a wandering character is "idle"
WANDER_JITTER_DEG = 220.0  # per second
SEPARATION_RADIUS = 48.0
SEPARATION_WEIGHT = 90.0
GROUP_SLOT_SPACING = SPRITE_W + 10
GROUP_ARRIVE_RADIUS = 4.0  # distance to a group slot below which we stop

# Animation
ANIM_FPS = 8.0  # clip playback rate (independent of render FPS)
HUG_DURATION = 1.2  # seconds

# Lifecycle
IDLE_TIMEOUT = 300.0  # seconds before an untouched character despawns
DESPAWN_SCAN_INTERVAL = 30.0  # seconds between despawn sweeps
MAX_CHARACTERS = 100  # soft cap; oldest-idle evicted past this

# Nameplate
NAMEPLATE_FONT_SIZE = 14
NAMEPLATE_COLOR = (235, 235, 235)
NAMEPLATE_OUTLINE = (0, 0, 0)
