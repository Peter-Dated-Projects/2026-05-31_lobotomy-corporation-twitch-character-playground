---
id: layer-scale-template-generalizes
root: gotchas
type: gotcha
status: current
summary: "The single LAYER_SCALES/LAYER_OFFSETS template calibrated for Standard Agent renders all 10 characters as recognizable chibis, because each layer type comes from one shared sheet at a consistent native size; only hair vertical offset varies enough to warrant per-character nudging."
related:
  - decisions/0003-per-layer-scale-on-4x-work-canvas
  - architecture/character-layer-stack
created: 2026-06-01
updated: 2026-06-01
---

# The per-layer scale template generalizes across all 10

Calibrating per-layer scales/offsets looks like it would be bespoke
per-character work. It is not. The values tuned for Standard Agent render
Officer Chesed, Officer Geburah, Panicked Worker, and Battle-Ready Agent (the
ones spot-checked) all as believable chibis -- correct head/body proportion,
faces sitting on the head, hair framing it, clothes below.

Why one template works: every character draws each layer type from the SAME
sheet (head is always `Head` v0, clothes torso is always an outfit-sheet v0 in
the 66-94px range, faces are always the small Eye/Brow/Mouth crops). Native
sizes per layer type are consistent across characters, so one scale factor per
layer fits everyone. The shared parts (head, body, limbs) are literally
identical sprites for all 10.

The one axis that varies enough to notice: **hair vertical position**. Different
hairstyles (front/rear hair variants) have different native heights and
baselines, so some sit slightly high or low on the head. If a future ticket
wants per-character polish, a small per-character `front_hair`/`rear_hair` dy
nudge is the highest-value lever; the scales themselves can stay global.

Verdict for the rollout: ship the global template, do NOT plan bespoke scale
tables per character. Budget only for optional per-character hair-offset tweaks.
