# Decisions

ADR-style records: what we chose and **why**. Name files with a zero-padded prefix,
e.g. `0001-single-git-tree.md`.

| Note | Summary | Status |
|---|---|---|
| [0001-hud-panel-layout-coordinate-independent](0001-hud-panel-layout-coordinate-independent.md) | HUD uses fixed panels (roster + command log) reading observable state defensively, not world-space sprite labels, to stay correct across coordinate/scene changes. | current |
| [0002-connected-component-extraction](0002-connected-component-extraction.md) | Use scipy connected-component bounding boxes to extract sprites from sheets rather than hardcoded coordinates, because all sheets share a white-background layout that makes position-independent extraction reliable. | current |
| [0003-per-layer-scale-on-4x-work-canvas](0003-per-layer-scale-on-4x-work-canvas.md) | Composite characters at 4x on a 128x160 work canvas with a per-layer scale (LAYER_SCALES), then smoothscale down to 32x40, because the raw extracted parts share no coordinate system and a single global scale cannot reconcile them. | current |
| [0004-layered-agent-behavior](0004-layered-agent-behavior.md) | Adopt a five-layer agent-behavior design — boids-lite ported to 1D-per-surface, brute-force O(N^2) neighbors at N=100, utility+threshold+hysteresis autonomy over a hard FSM, valence/arousal emotion, and appearance-decorrelated md5 trait seeding — over the heavier textbook alternatives. | current |
| [0005-personality-skew-direction](0005-personality-skew-direction.md) | personality_for up-skews sociability (sqrt) and down-skews independence (square) so loners are a thin minority — the inverse of the research brief's literal "square the sociability draw", which would make loners the majority; we followed the brief's stated intent over its example. | current |
| [0006-1d-grid-neighbor-query](0006-1d-grid-neighbor-query.md) | Replace brute-force O(N^2) per-frame neighbour scanning with the 1D horizontal bucket grid (own cell +/-1, cell sized to max interaction radius), superseding the perf clause of 0004 once the crowd cap exceeded the frame budget; ~3x faster, density-bounded. | current |
| [0007-command-channel-model](0007-command-channel-model.md) | Commands arrive as free in-channel chat commands (e.g. !join) read via EventSub channel.chat.message; whisper-as-command-channel is rejected (40 unique recipients/day send cap), and Channel Points redeems are reserved for future opt-in gated actions. | current |
| [0008-python-312-required-for-speak](0008-python-312-required-for-speak.md) | The speak feature forced requires-python from >=3.10 to >=3.12,<3.13 because kanade-tokenizer (KokoClone's voice-conversion model) hard-requires Python >=3.12; all pre-existing deps are 3.12-safe and the full test suite passes. | current |
