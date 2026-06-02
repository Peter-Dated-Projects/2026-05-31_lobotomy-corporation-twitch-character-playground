---
id: 0002-connected-component-extraction
root: decisions
type: decision
status: current
summary: "Use scipy connected-component bounding boxes to extract sprites from sheets rather than hardcoded coordinates, because all sheets share a white-background layout that makes position-independent extraction reliable."
related:
  - architecture/sprite-extraction-algorithm
  - domain/lobcorp-sprite-sheet-catalog
created: 2026-06-01
updated: 2026-06-01
---

# Decision: connected-component extraction over hardcoded coordinates

## Context

LobCorp sprite sheets pack sprites loosely on a white background with whitespace gaps. There are ~60 sheets across two folders. We needed an extraction strategy before writing the renderer.

## Options considered

1. **Hardcode crop rects per sheet** — precise but brittle; any re-export of a sheet breaks all coordinates, and maintaining 60 coordinate tables is unreasonable.
2. **Uniform grid slicing** — sheets are not uniformly gridded (sprites vary in size and position), so this produces partial or mis-aligned crops.
3. **Connected-component bounding boxes (chosen)** — scan for non-white, non-transparent pixels; label connected blobs; extract bounding boxes; sort in reading order. Works on any sheet in the folder without configuration.

## Decision

Use scipy `ndimage.label` on a white+transparent mask. Noise filtered by minimum blob size (5x5 px). Row grouping by 60px tolerance for reading-order sort.

## Consequences

- Any sheet can be added to the asset folder without code changes.
- Variant indices (0, 1, 2…) depend on reading order — if a sheet is reorganized, indices shift. This is documented in the sprite catalog and clothes sheet layout.
- Requires `scipy` and `pillow` as runtime dependencies.
