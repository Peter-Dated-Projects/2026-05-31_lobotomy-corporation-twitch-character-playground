---
id: character-layer-stack
root: architecture
type: architecture
status: current
summary: "Characters are composited from 10 ordered layers blitted onto a shared canvas; face layers swap by emotion state, limb layers advance by animation frame."
related:
  - domain/lobcorp-sprite-sheet-catalog
  - architecture/sprite-extraction-algorithm
  - conventions/character-def-format
created: 2026-06-01
updated: 2026-06-01
---

# Character Layer Stack

Every character is assembled per-frame by blitting sprites in this order onto a transparent canvas of size `(SPRITE_W, SPRITE_H)`:

| # | Layer | Source | Varies by |
|---|---|---|---|
| 1 | Rear hair | `Credit_RearHair` sheet, fixed variant | character def |
| 2 | Body limbs (bare) | `skeleton2`, variant = `anim_frame % 7` | anim frame |
| 3 | Clothes limbs | outfit sheet, variant = `3 + (anim_frame % 8)` | anim frame |
| 4 | Body torso (bare) | `skeleton` variant 0 | static |
| 5 | Clothes torso | outfit sheet variant 0 | character def |
| 6 | Head circle | `Head` variant 0 | static |
| 7 | Front hair | `Credit_FrontHair` sheet, fixed variant | character def |
| 8 | Eyebrows | `EyeBrow_*` sheet, keyed by emotion state | emotion + char def |
| 9 | Eyes | `Eye_*` sheet, keyed by emotion state | emotion + char def |
| 10 | Mouth | `Mouth_*` sheet, keyed by emotion state | emotion + char def |
| 11 | Glasses | optional overlay | character def |
| 12 | Weapon | side-offset sprite | character def |

## Compositing space (4x work canvas + per-layer scale)

The parts share no coordinate system (head ~193px wide, torso ~66px, mouth
~11px in native px), so compositing happens at 4x on a `WORK_W x WORK_H`
(128x160) canvas: each layer is first scaled by `settings.LAYER_SCALES[layer]`
(a multiplier on its native size), placed at the work-center plus its
`LAYER_OFFSETS` entry, then the finished composite is `smoothscale`d down to
(SPRITE_W, SPRITE_H). See decision 0003 for the rationale. Both dicts are
tunable constants in settings.py — do not hardcode inline.

Calibrated values for Standard Agent (work-canvas px; this is the global
template, which renders all 10 believably — see the layer-scale-template
gotcha):

```
layer          scale   offset(dx,dy)
rear_hair      0.26    (0,  -34)
body_limbs     1.7     (0,  +44)
clothes_limbs  1.05    (0,  +44)
body_torso     1.05    (0,  +24)
clothes_torso  0.74    (0,  +26)
head           0.30    (0,  -26)
front_hair     0.27    (0,  -40)
eyebrows       0.9     (0,  -31)
eyes           0.9     (0,  -24)
mouth          0.95    (0,  -11)
weapon         0.4     (+34, +18)
```

## Emotion states

Three states drive face layer selection: `"default"`, `"battle"`, `"panic"`. Each maps to a different eye/eyebrow/mouth sheet. The state is passed in at render time, not baked into the SpriteSet.

## Animation clips

| Clip | Frames | Notes |
|---|---|---|
| idle | 2 | anim_frame 0; frame 1 shifts torso 1px up for breathing bob |
| walk | 8 | anim_frames 0-7, emotion=default |
| run | 8 | anim_frames 0-7, torso leaned +3px forward |
| hug | 4 | anim_frame 0; clothes torso scaled 1.0→1.2→1.4→1.2 wide across frames |
