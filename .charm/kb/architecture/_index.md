# Architecture

How the system is actually built -- components, data flow, the mental model.

| Note | Summary | Status |
|---|---|---|
| [character-layer-stack](character-layer-stack.md) | Characters are composited from 10 ordered layers blitted onto a shared canvas; face layers swap by emotion state, limb layers advance by animation frame. | current |
| [sprite-extraction-algorithm](sprite-extraction-algorithm.md) | Sprites are extracted from sheets using scipy connected-component bounding boxes on the non-white non-transparent mask, sorted in reading order with a 60px row-grouping tolerance. | current |
| [agent-behavior-model](agent-behavior-model.md) | The five-layer agent-behavior design (steering core, velocity facing, crowd awareness, seeded personality, emotion) that builds on one shared per-frame neighbor scan and one widened World.update signature. | current |
