# Decisions

ADR-style records: what we chose and **why**. Name files with a zero-padded prefix,
e.g. `0001-single-git-tree.md`.

| Note | Summary | Status |
|---|---|---|
| [0001-hud-panel-layout-coordinate-independent](0001-hud-panel-layout-coordinate-independent.md) | HUD uses fixed panels (roster + command log) reading observable state defensively, not world-space sprite labels, to stay correct across coordinate/scene changes. | current |
| [0002-connected-component-extraction](0002-connected-component-extraction.md) | Use scipy connected-component bounding boxes to extract sprites from sheets rather than hardcoded coordinates, because all sheets share a white-background layout that makes position-independent extraction reliable. | current |
| [0003-per-layer-scale-on-4x-work-canvas](0003-per-layer-scale-on-4x-work-canvas.md) | Composite characters at 4x on a 128x160 work canvas with a per-layer scale (LAYER_SCALES), then smoothscale down to 32x40, because the raw extracted parts share no coordinate system and a single global scale cannot reconcile them. | current |
