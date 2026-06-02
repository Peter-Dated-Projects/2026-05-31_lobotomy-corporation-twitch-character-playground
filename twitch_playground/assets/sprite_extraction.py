"""Sprite-sheet extraction for the real LobCorp art pipeline.

LobCorp sheets pack sprites loosely on a white background with whitespace gaps.
Rather than maintain ~60 hand-tuned coordinate tables, we find sprites
automatically: mask out white + transparent pixels, label the remaining
connected blobs, take each blob's bounding box, and sort the boxes into reading
order. See the architecture KB note for the rationale.

Importing this module is side-effect free: no filesystem reads, no pygame
display, no asset existence checks. All of that happens lazily when a function
or SpriteSheetCache method is actually called.
"""

from __future__ import annotations

import os

import numpy as np
import pygame
from PIL import Image
from scipy import ndimage

from twitch_playground import settings


def extract_sprites(path: str) -> list[Image.Image]:
    """Find and crop every sprite on a white-background sheet, in reading order.

    A blob is anything that is neither (near-)transparent nor (near-)white.
    Blobs smaller than 5px in either dimension are discarded as noise. Boxes are
    ordered top-to-bottom in rows (bucketed by SHEET_ROW_TOLERANCE) then
    left-to-right within each row.
    """
    img = Image.open(path).convert("RGBA")
    arr = np.array(img)

    is_transparent = arr[:, :, 3] < 10
    is_white = (
        (arr[:, :, 0] > 240)
        & (arr[:, :, 1] > 240)
        & (arr[:, :, 2] > 240)
        & (arr[:, :, 3] > 240)
    )
    mask = ~(is_transparent | is_white)

    labeled, n = ndimage.label(mask)

    boxes: list[tuple[int, int, int, int]] = []
    for i in range(1, n + 1):
        rows, cols = np.where(labeled == i)
        y1, y2 = rows.min(), rows.max()
        x1, x2 = cols.min(), cols.max()
        if (y2 - y1) > 5 and (x2 - x1) > 5:  # filter noise
            boxes.append((y1, x1, y2 + 1, x2 + 1))

    tol = settings.SHEET_ROW_TOLERANCE
    boxes.sort(key=lambda b: (b[0] // tol, b[1]))

    return [img.crop((x1, y1, x2, y2)) for y1, x1, y2, x2 in boxes]


def pil_to_surface(img: Image.Image) -> pygame.Surface:
    """Convert a PIL image to a display-ready pygame Surface.

    Requires an active pygame video mode (convert_alpha binds to it), so call
    this only after pygame.display.set_mode().
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return pygame.image.frombytes(img.tobytes(), img.size, "RGBA").convert_alpha()


class SpriteSheetCache:
    """Lazily loads and extracts each sheet once, indexing all variants.

    A bare filename (e.g. "Agent-resources.assets-1521.png") is resolved against
    both the parts and clothes asset folders. Extracted variants are exposed as
    pygame Surfaces keyed by (filename, variant_index); the underlying sheet is
    read and segmented only on first access.
    """

    def __init__(self) -> None:
        self._sheets: dict[str, list[pygame.Surface]] = {}

    def _resolve(self, filename: str) -> str:
        """Find a bare filename under PARTS_DIR or CLOTHES_DIR."""
        for root in (settings.PARTS_DIR, settings.CLOTHES_DIR):
            candidate = os.path.join(root, filename)
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError(
            f"sprite sheet {filename!r} not found in {settings.PARTS_DIR!r} "
            f"or {settings.CLOTHES_DIR!r}"
        )

    def _load(self, filename: str) -> list[pygame.Surface]:
        if filename not in self._sheets:
            path = self._resolve(filename)
            self._sheets[filename] = [pil_to_surface(s) for s in extract_sprites(path)]
        return self._sheets[filename]

    def get(self, filename: str, variant_index: int) -> pygame.Surface:
        """Return one extracted sprite from a sheet, loading it on first access."""
        return self._load(filename)[variant_index]

    def variant_count(self, filename: str) -> int:
        """Number of sprites extracted from a sheet (loads it if needed)."""
        return len(self._load(filename))
