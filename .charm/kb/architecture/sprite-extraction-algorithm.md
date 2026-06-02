---
id: sprite-extraction-algorithm
root: architecture
type: architecture
status: current
summary: "Sprites are extracted from sheets using scipy connected-component bounding boxes on the non-white non-transparent mask, sorted in reading order with a 60px row-grouping tolerance."
related:
  - domain/lobcorp-sprite-sheet-catalog
  - decisions/0002-connected-component-extraction
created: 2026-06-01
updated: 2026-06-01
---

# Sprite Extraction Algorithm

All LobCorp sprite sheets use a **white background** with whitespace gaps between sprites. No hardcoded coordinates are needed — sprites are found automatically.

## Algorithm

```python
from PIL import Image
import numpy as np
from scipy import ndimage

ROW_TOLERANCE = 60  # px; sprites within this vertical range are treated as one row

def extract_sprites(path: str) -> list[Image.Image]:
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)

    is_transparent = arr[:, :, 3] < 10
    is_white = (arr[:, :, 0] > 240) & (arr[:, :, 1] > 240) & \
               (arr[:, :, 2] > 240) & (arr[:, :, 3] > 240)
    mask = ~(is_transparent | is_white)

    labeled, n = ndimage.label(mask)

    boxes = []
    for i in range(1, n + 1):
        rows, cols = np.where(labeled == i)
        y1, y2 = rows.min(), rows.max()
        x1, x2 = cols.min(), cols.max()
        if (y2 - y1) > 5 and (x2 - x1) > 5:   # filter noise
            boxes.append((y1, x1, y2 + 1, x2 + 1))

    # reading order: row bucket by top coordinate, then left-to-right
    boxes.sort(key=lambda b: (b[0] // ROW_TOLERANCE, b[1]))

    return [img.crop((x1, y1, x2, y2)) for y1, x1, y2, x2 in boxes]
```

## Known sprite index layout for clothes sheets

For every outfit sheet (`Agent-*`, `Officer_*`), extracted sprites in reading order map to:
- Index 0: torso
- Indices 1-2: hands
- Indices 3-10: 8 animation limb frames (walk cycle)

## PIL -> pygame conversion

```python
def pil_to_surface(img: Image.Image) -> pygame.Surface:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return pygame.image.frombytes(img.tobytes(), img.size, "RGBA").convert_alpha()
```

## Caching

A `SpriteSheetCache` wraps `extract_sprites`, loading each sheet once on first access and indexing all variants. Cache is keyed by `(filename, variant_index)`.
