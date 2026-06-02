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

## Anchor offsets (relative to canvas center, y up = negative)

```
rear_hair:    (0,   0)
body limbs:   (0, +10)
clothes limbs:(0, +10)
body torso:   (0,   0)
clothes torso:(0,   0)
head:         (0, -30)
front_hair:   (0, -50)
eyebrows:     (0, -42)
eyes:         (0, -28)
mouth:        (0, -10)
weapon:       (+20, +5)
```

These are tunable constants — do not hardcode inline.

## Emotion states

Three states drive face layer selection: `"default"`, `"battle"`, `"panic"`. Each maps to a different eye/eyebrow/mouth sheet. The state is passed in at render time, not baked into the SpriteSet.

## Animation clips

| Clip | Frames | Notes |
|---|---|---|
| idle | 2 | anim_frame 0; frame 1 shifts torso 1px up for breathing bob |
| walk | 8 | anim_frames 0-7, emotion=default |
| run | 8 | anim_frames 0-7, torso leaned +3px forward |
| hug | 4 | anim_frame 0; clothes torso scaled 1.0→1.2→1.4→1.2 wide across frames |
