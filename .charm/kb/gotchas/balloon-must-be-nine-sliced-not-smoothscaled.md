---
id: balloon-must-be-nine-sliced-not-smoothscaled
root: gotchas
type: gotcha
status: current
summary: "The speak balloon art (assets/robots/balloon.png) is a tiny 101x101 flat panel with an ~8px coral border, so resizing it for arbitrary text must 9-slice it (native-scale corners, stretch edges/center) -- a plain smoothscale distorts the border into uneven thicknesses."
created: 2026-06-07
updated: 2026-06-07
---

`render/speech.py` sizes the speech balloon to fit each wrapped message, but the
source art `assets/robots/balloon.png` is only 101x101: a flat gray fill with a
flat ~8px coral border, no tail, no rounded corners (see
`kb/robot-sprite-candidates.md`).

Scaling it up with `pygame.transform.smoothscale` would scale the border
uniformly with the panel, so a wide-short balloon ends up with a thick
left/right border and a thin top/bottom one -- visibly wrong. The fix is a
9-slice (`_scale_balloon`): keep the four corners at native scale, stretch each
edge along its single axis, and stretch the center both ways. Because the panel
is a flat color, this reads as a crisp uniform-border rect at any size.

`_BALLOON_BORDER = 8` is the native corner inset the 9-slice keys off. If the
balloon art is ever re-vendored with a different border width or rounded
corners, that constant (and the flat-panel assumption) must be revisited.

Related: robot bodies in the same module are scaled by `settings.SCREEN_H *
_ROBOT_HEIGHT_FRAC`, not a hardcoded px -- the original ticket referenced a stale
1920x200 stage, but the live stage is 510x120, so always scale relative to
`settings.SCREEN_W/SCREEN_H`.
