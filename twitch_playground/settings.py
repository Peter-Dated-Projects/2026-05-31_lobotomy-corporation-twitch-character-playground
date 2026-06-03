"""Flat module-level configuration. Override in tests by reassigning."""

import os

# Window / render
SCREEN_W = 850  # compact stage; the OS window is resizable and scales this up
SCREEN_H = 200  # taller band than before -> more vertical headroom; the level
#                 (GROUND_TOP / JUMP_SPEED / default_level below) is tuned for it
FPS = 12  # deliberate low-fps / stop-motion look; movement is delta-time based
CAPTION = "LobCorp Twitch Playground"
BG_COLOR = (24, 26, 32)
WALL_MARGIN = 36  # characters bounce / clamp inside this inset

# Sprite
SPRITE_W = 32
SPRITE_H = 40

# Movement (px/sec, since we integrate with delta-time)
MAX_SPEED = 70.0  # hard cap on horizontal velocity magnitude (slightly above
#                   WALK_SPEED so a separation nudge can briefly add on top)
WALK_THRESHOLD = 8.0  # speed below which a wandering character is "idle"
GROUP_SLOT_SPACING = SPRITE_W + 10
GROUP_ARRIVE_RADIUS = 4.0  # distance to a group slot below which we stop
GROUP_SLOW_RADIUS = 28.0  # arrive: inside this radius desired speed scales
#                           linearly to 0 before the GROUP_ARRIVE_RADIUS snap

# Acceleration easing. Velocity eases toward a desired value with a capped
# steering force (Reynolds: steering = desired - current, clamped to MAX_FORCE)
# instead of snapping, so starts and stops read as weight. Tuned so a character
# ramps from rest to WALK_SPEED in ~0.25s (a few frames at the 12fps render).
MAX_FORCE = 240.0  # px/s^2; cap on how sharply horizontal velocity can change

# Sidescroller physics (px, px/s, px/s^2). Smaller y is higher on screen, so a
# jump is a negative y velocity and gravity is positive.
GROUND_TOP = SCREEN_H - 40  # feet-y of the ground surface; leaves a ~40px ground
#                             band at the bottom and ~260px of headroom above it
#                             for the floating tier + jump arc.
GRAVITY = 1200.0
JUMP_SPEED = 480.0  # initial hop speed; apex ~JUMP_SPEED^2/(2*GRAVITY) ~= 96px.
#                     Clears the floating tier's 70px gap with ~26px margin, so
#                     that tier stays reachable in one jump from the ground.
WALK_SPEED = 60.0  # horizontal stroll speed on a surface

# Wander decisions. Chances are per-second and multiplied by dt for a per-frame
# probability, so behaviour is independent of frame rate.
JUMP_CHANCE = 0.45  # hops per second while grounded and strolling
IDLE_CHANCE = 0.18  # idle-pause starts per second while grounded (low: keep roaming)
IDLE_PAUSE_MIN = 0.6
IDLE_PAUSE_MAX = 1.8

# Coherent 1-D wander: a persistent heading (signed desired speed) that drifts a
# little each frame instead of being re-rolled with random.choice. The small
# per-frame drift keeps meandering coherent (long-term wander, short-term
# stability); the occasional reorientation lets a character change its mind.
WANDER_DISPLACE = 140.0  # px/s of heading drift per second (random-walk magnitude)
WANDER_REORIENT_CHANCE = 0.8  # per-second chance of a larger heading reorientation

# Horizontal separation so characters sharing a surface do not fully overlap.
# Purely horizontal: only neighbours at a similar height (same surface) push.
HSEP_RADIUS = 30.0  # px; only neighbours closer than this nudge us apart
HSEP_Y_BAND = 12.0  # px; only neighbours within this height band count
HSEP_PUSH = 40.0  # px/s; max horizontal nudge applied

# Crowd awareness (Reynolds boids beyond separation). All three rules are
# horizontal and same-surface (reuse HSEP_Y_BAND), all fed from the ONE shared
# per-frame neighbour-record list. Mirrors the HSEP_* block above; liveliness
# lives in these weights, so expect to tune by eye. The final crowd force is a
# separation-dominant weighted blend clamped to CROWD_MAX_NUDGE:
#   crowd = SEP_WEIGHT*separation + COH_WEIGHT*cohesion + ALI_WEIGHT*alignment
CROWD_SEP_WEIGHT = 1.0  # separation is the collision-avoider, kept dominant
CROWD_COH_WEIGHT = 0.0  # off: cohesion no longer pulls characters into packs
CROWD_ALI_WEIGHT = 0.0  # off: alignment no longer homogenizes local heading
CROWD_COH_RADIUS = 80.0  # px; cohesion looks further than separation
CROWD_ALI_RADIUS = 80.0  # px; alignment looks further than separation
CROWD_DENSITY_RADIUS = 60.0  # px; same-band neighbour count window
CROWD_MAX_NUDGE = 50.0  # px/s; clamp on the summed crowd force

# Local-density response (SFM): a packed platform shuffles instead of marching.
CROWD_SLOWDOWN_PER_NEIGHBOR = 0.03  # walk-speed fraction trimmed per same-band neighbour
CROWD_MIN_SPEED_SCALE = 0.7  # floor on the density slowdown so packed characters keep most speed
CROWD_JUMP_DENSITY = 2  # suppress hops once this many neighbours are packed in
CROWD_IDLE_DENSITY_GAIN = 0.15  # IDLE_CHANCE multiplier added per neighbour (mild extra pause when packed)

# Personality (L4): per-character traits + autonomous follow/leave. Traits are
# derived deterministically from the username (see sim/personality.py) and bias a
# low-frequency utility check that joins/leaves clusters on its own, layered onto
# the command-driven FSM without replacing it. Liveliness lives in these knobs;
# expect to tune by eye.
AUTONOMOUS_GROUPING = False  # off: characters never self-form clusters (explicit !follow still works)
MAX_JOIN_THRESHOLD = 5  # Granovetter ceiling: the most solitary character needs a
#                         knot of up to 1 + this many same-surface peers to join
DECIDE_INTERVAL = 0.4  # s between autonomous decisions (~2.5 Hz); cheap, and the
#                        low cadence doubles as oscillation damping
JOIN_RADIUS = 140.0  # px; same-surface horizontal reach for sensing a cluster
JOIN_ENTER_SCORE = 0.4  # join utility must clear this to autonomously join
LEAVE_SCORE = 0.4  # leave utility must clear this to autonomously leave
JOIN_DWELL = 3.0  # min s grouped before a leave check may fire (commit dwell)
LEAVE_DWELL = 2.0  # min s wandering before a join check may fire (rejoin cooldown)
MANUAL_HOLD_DURATION = 8.0  # s a chat command suppresses the autonomous check, so
#                             the AI never immediately undoes a viewer's !follow/!leave
RESTLESS_RATE_SPAN = 2.0  # restlessness in [0,1] maps to a [0, SPAN] multiplier on
#                           JUMP_CHANCE / IDLE_CHANCE, so the median character keeps
#                           ~the global rate while calm/restless ones visibly diverge

# Emotion (L5): a continuous (valence, arousal) state per character, orthogonal
# to the behaviour Mode, that drives the face and modulates movement. Updated
# every frame from three sources -- exponential decay toward neutral, proximity-
# weighted contagion from neighbours, and a mild crowding arousal bump -- then
# quantized to the three existing faces with hysteresis. Conservative defaults:
# the contagion lag and decay are what sell the effect, and decay MUST outrun
# contagion at the crowd's resting state or panic latches forever. Tune by eye.
EMOTION_DECAY_PER_SEC = 0.4  # fraction of an emotion value retained per second
#                              (spiky/fast: ~40% survives each second toward neutral)
CONTAGION_RATE = 0.2  # how fast I move toward my neighbours' mood per second
#                       (low: mood no longer homogenizes the crowd into a frozen sync)
CONTAGION_RADIUS = 2.5 * SPRITE_W  # px; only fairly close neighbours infect me
AROUSAL_SPEED_GAIN = 0.8  # arousal=1 walks up to ~1.8x WALK_SPEED (and lifts the cap)
CROWD_AROUSAL = 0.05  # arousal added per in-radius neighbour per second (crowd tension)
VALENCE_SPEED_DAMP = 0.5  # distress (negative valence) damps speed: valence=-1 -> x0.5
AROUSAL_RESTLESS_GAIN = 1.0  # arousal raises JUMP cadence / lowers IDLE cadence by this
VALENCE_SEP_GAIN = 0.5  # valence scales separation: happy(+1) x0.5 (tighter),
#                         distressed(-1) x1.5 (withdraw / want more space)
EMOTION_TRAIT_MIN = 0.5  # seeded susceptibility/expressiveness map into [MIN, 1.0]

# Face quantization hysteresis (dual enter/exit thresholds so faces don't strobe
# when a value sits on a boundary). A face is harder to enter than to leave: the
# EXIT thresholds are looser, so a face holds through small dips back across the
# boundary. panic = distressed + agitated; battle = high arousal; else default.
PANIC_VALENCE_ENTER = -0.35
PANIC_VALENCE_EXIT = -0.20
PANIC_AROUSAL_ENTER = 0.40
PANIC_AROUSAL_EXIT = 0.25
BATTLE_AROUSAL_ENTER = 0.50
BATTLE_AROUSAL_EXIT = 0.35

# Spatial acceleration (1D horizontal bucket grid). The per-frame neighbour
# interaction was O(N^2) -- every character vs every other -- which is the wall on
# crowd size. Because motion is surface-bound and ~1D-per-surface, World.update
# buckets characters by floor(pos.x / GRID_CELL) once per frame and hands each one
# only its own bucket +/- 1 as candidate neighbours (a near-constant-time lookup
# instead of the full list). Defined here, below the radii it depends on.
#
# CORRECTNESS INVARIANT: GRID_CELL must be >= the largest interaction radius any
# consumer uses. With cell >= max radius, every neighbour within that radius is
# guaranteed to fall in the agent's own cell or an adjacent one, so the bucket
# +/-1 candidate slice loses nobody. We derive it from the live radii (rather than
# hardcoding) so it stays correct if any radius is retuned -- adding a wider-radius
# rule auto-widens the cell.
GRID_CELL = max(
    HSEP_RADIUS,
    CROWD_COH_RADIUS,
    CROWD_ALI_RADIUS,
    CROWD_DENSITY_RADIUS,
    CONTAGION_RADIUS,
)

# Command-driven emotion impulses (an OCC-style appraised event: an instantaneous
# clamped nudge to the target's valence/arousal). !hug also keeps its EMOTING clip.
HUG_VALENCE_IMPULSE = 0.4
PANIC_AROUSAL_IMPULSE = 0.8
PANIC_VALENCE_IMPULSE = -0.7
CHEER_AROUSAL_IMPULSE = 0.5
CHEER_VALENCE_IMPULSE = 0.6

# Animation
ANIM_FPS = 8.0  # clip playback rate (independent of render FPS)
HUG_DURATION = 1.2  # seconds
# Per-second multiplier easing residual horizontal motion to a stop while
# EMOTING (was a frame-rate-dependent ``*= 0.6`` per frame). Applied as
# ``velocity.x *= EMOTE_DECAY_PER_SEC ** dt`` so the decay is identical at any
# frame rate; ~0.0022 reproduces the old 0.6/frame feel at the 12fps render.
EMOTE_DECAY_PER_SEC = 0.0022

# Lifecycle
IDLE_TIMEOUT = 1800.0  # seconds (30 min) before an untouched character despawns;
#                        ANY command (spawn/hug/follow/cheer/...) calls touch() and
#                        resets this, so a character only drops after 30 min of silence
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
