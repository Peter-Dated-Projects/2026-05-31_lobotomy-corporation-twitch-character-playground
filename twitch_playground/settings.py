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
GROUP_SLOT_SPACING = SPRITE_W + 10
GROUP_ARRIVE_RADIUS = 4.0  # distance to a group slot below which we stop

# Sidescroller physics (px, px/s, px/s^2). Smaller y is higher on screen, so a
# jump is a negative y velocity and gravity is positive.
GROUND_TOP = SCREEN_H - 60  # feet-y of the ground surface
GRAVITY = 1200.0
JUMP_SPEED = 580.0  # initial hop speed; apex ~JUMP_SPEED^2/(2*GRAVITY) ~= 140px,
#                     comfortably above the 95px gap between platform tiers, so
#                     every tier is reachable in a single jump from the one below.
WALK_SPEED = 60.0  # horizontal stroll speed on a surface

# Wander decisions. Chances are per-second and multiplied by dt for a per-frame
# probability, so behaviour is independent of frame rate.
JUMP_CHANCE = 0.45  # hops per second while grounded and strolling
IDLE_CHANCE = 0.30  # idle-pause starts per second while grounded
IDLE_PAUSE_MIN = 0.6
IDLE_PAUSE_MAX = 1.8

# Horizontal separation so characters sharing a surface do not fully overlap.
# Purely horizontal: only neighbours at a similar height (same surface) push.
HSEP_RADIUS = 30.0  # px; only neighbours closer than this nudge us apart
HSEP_Y_BAND = 12.0  # px; only neighbours within this height band count
HSEP_PUSH = 40.0  # px/s; max horizontal nudge applied

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
