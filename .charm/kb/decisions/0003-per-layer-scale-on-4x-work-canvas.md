---
id: 0003-per-layer-scale-on-4x-work-canvas
root: decisions
type: decision
status: current
summary: "Composite characters at 4x on a 128x160 work canvas with a per-layer scale (LAYER_SCALES), then smoothscale down to 32x40, because the raw extracted parts share no coordinate system and a single global scale cannot reconcile them."
related:
  - architecture/character-layer-stack
  - decisions/0002-connected-component-extraction
created: 2026-06-01
updated: 2026-06-01
---

# Per-layer scale on a 4x work canvas

## Context

compose_character originally blitted full-resolution part crops directly onto
the 32x40 sprite canvas with no per-layer scale, so every character rendered as
an overflowing blob. The root cause runs deeper than "too big": the extracted
parts do not share a coordinate system. Measured native sizes for Standard
Agent (real sheets, 2026-06-01):

| Part | native px |
|---|---|
| Head (Head v0) | 193x200 |
| Front hair (Credit_FrontHair v0) | 235x215 |
| Rear hair (Credit_RearHair v0) | 71x275 |
| Clothes torso (Agent v0) | 66x94 |
| Clothes limb (Agent v3) | 23x44 |
| Body torso (skeleton v0) | 25x33 |
| Body limb (skeleton2 v0) | 16x11 |
| Eyes (Eye_Default_1 v0) | 23x26 |
| Eyebrow (EyeBrow_1 v0) | 19x7 |
| Mouth (Mouth_1 v0) | 11x9 |

The head is ~3x wider than the torso and ~8x wider than the mouth in native
px. A single global downscale that makes the head fit shrinks the face features
to nothing, and vice versa. The face/head/body layers were each authored at a
different resolution in the original game art.

## Decision

Composite on a working canvas 4x the sprite size (`WORK_W=128, WORK_H=160`,
same 32:40 aspect). Each layer is first scaled by its own factor from
`settings.LAYER_SCALES` (a multiplier on the part's native size) before being
blitted centered at the work-canvas center plus its `LAYER_OFFSETS` entry (now
expressed in work-canvas px). After all layers are placed, the finished
composite is `smoothscale`d down to (SPRITE_W, SPRITE_H) as the final step --
the size every clip frame must be.

smoothscale (not nearest `scale`) is used both per-part on the way down from the
100-275px native crops and for the final composite shrink, so the dense face
features antialias into something legible at 32x40 instead of aliasing to noise.

The 32x40 clip-frame contract is unchanged downstream; only the internal
build pipeline moved to the larger intermediate space.

## Consequence

Standard Agent now renders as a recognizable chibi (pale face, dark hair frame,
two eyes + small mouth, dark suit with red tie, pistol at side) rather than a
blob -- verified visually. See the gotcha note on bespoke-vs-template scaling
for whether the calibrated values generalize to the other 9 characters.
