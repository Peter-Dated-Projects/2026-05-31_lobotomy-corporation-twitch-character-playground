"""Flat module-level configuration. Override in tests by reassigning."""

import os

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

# --- LobCorp sprite assets ---------------------------------------------------
# Root of the extracted sprite-sheet drop. Override with LOBCORP_ASSETS_ROOT to
# point at a different checkout; nothing here touches the filesystem at import
# time -- only the extraction layer reads these on demand.
ASSETS_ROOT = os.environ.get(
    "LOBCORP_ASSETS_ROOT",
    os.path.expanduser("~/Downloads/drive-download-20260601T210823Z-3-001"),
)
PARTS_DIR = os.path.join(ASSETS_ROOT, "Employee Parts")
CLOTHES_DIR = os.path.join(ASSETS_ROOT, "Employee Clothes and Weapons")

# Sprites within this vertical range are treated as one row when sorting
# extracted blobs into reading order.
SHEET_ROW_TOLERANCE = 60

# --- Compositing coordinate system ------------------------------------------
# The raw extracted parts share NO coordinate system: a character's head crop is
# ~193px wide, its torso ~66px, its eyes ~23px (measured on Standard Agent's real
# sheets). Blitting them at native size onto the 32x40 sprite canvas just
# overflows into a blob. So we composite at 4x on a larger WORKING canvas, where
# each layer is first scaled by its own LAYER_SCALES factor into a shared space,
# then downscale the finished composite to (SPRITE_W, SPRITE_H) -- the size every
# clip frame must be. y grows downward throughout; offsets below are in
# working-canvas pixels relative to its center.
WORK_W = SPRITE_W * 4  # 128
WORK_H = SPRITE_H * 4  # 160

# Per-layer scale: a multiplier on each part's NATIVE extracted size, chosen so
# the disparate-resolution parts land in one believable proportion on the work
# canvas. Calibrated visually for "Standard Agent" (the proof character); the
# other named characters reuse these and may need bespoke tuning later. A layer
# missing from the dict scales 1:1. Tunable -- never hardcode inline.
LAYER_SCALES = {
    "rear_hair": 0.26,
    "body_limbs": 1.7,
    "clothes_limbs": 1.05,
    "body_torso": 1.05,
    "clothes_torso": 0.74,
    "head": 0.30,
    "front_hair": 0.27,
    "eyebrows": 0.9,
    "eyes": 0.9,
    "mouth": 0.95,
    "weapon": 0.4,
}

# Per-layer anchor offset (dx, dy) relative to the WORK canvas center, applied
# after a layer is scaled. y grows downward, so a negative dy lifts a layer up.
# Tunable -- never hardcode these inline in the renderer.
LAYER_OFFSETS = {
    "rear_hair": (0, -34),
    "body_limbs": (0, 44),
    "clothes_limbs": (0, 44),
    "body_torso": (0, 24),
    "clothes_torso": (0, 26),
    "head": (0, -26),
    "front_hair": (0, -40),
    "eyebrows": (0, -31),
    "eyes": (0, -24),
    "mouth": (0, -11),
    "weapon": (34, 18),
}
