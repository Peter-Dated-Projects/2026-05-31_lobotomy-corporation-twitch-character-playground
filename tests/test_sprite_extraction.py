"""Headless tests for the sprite extraction algorithm.

These never touch a display or any real LobCorp asset: each test synthesizes a
white-background RGBA sheet with solid colored rectangles at known positions in
tmp_path, then asserts the blob count and the reading order returned by
extract_sprites. Reading order is verified by tagging every rectangle with a
unique color and reading back the dominant color of each extracted crop.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from twitch_playground.assets.sprite_extraction import extract_sprites

# Distinct opaque colors, none of them white, so each rect is its own blob and
# is identifiable in the output by its color alone.
COLORS = [
    (200, 30, 30, 255),
    (30, 200, 30, 255),
    (30, 30, 200, 255),
    (200, 200, 30, 255),
    (200, 30, 200, 255),
    (30, 200, 200, 255),
]


def _sheet(size, rects, path):
    """Write a white RGBA sheet with the given (x, y, w, h, color) rects."""
    arr = np.full((size[1], size[0], 4), 255, dtype=np.uint8)
    for x, y, w, h, color in rects:
        arr[y : y + h, x : x + w] = color
    Image.fromarray(arr, "RGBA").save(path)
    return str(path)


def _dominant(img: Image.Image) -> tuple[int, int, int, int]:
    """The most common pixel color in a crop (the rect fills most of its box)."""
    arr = np.array(img.convert("RGBA")).reshape(-1, 4)
    colors, counts = np.unique(arr, axis=0, return_counts=True)
    return tuple(int(c) for c in colors[counts.argmax()])


def test_single_row_reading_order(tmp_path):
    # Three rects on one row, deliberately authored out of left-to-right order
    # to prove the sort -- placed by x = 10, 120, 60 with colors 0, 1, 2.
    rects = [
        (10, 20, 30, 30, COLORS[0]),
        (120, 20, 30, 30, COLORS[1]),
        (60, 20, 30, 30, COLORS[2]),
    ]
    path = _sheet((200, 80), rects, tmp_path / "single.png")

    sprites = extract_sprites(path)

    assert len(sprites) == 3
    # Expected left-to-right by x: 10 -> 60 -> 120, i.e. colors 0, 2, 1.
    assert [_dominant(s) for s in sprites] == [COLORS[0], COLORS[2], COLORS[1]]


def test_two_row_grouping(tmp_path):
    # Row 1 near the top (y=10), row 2 well below the 60px tolerance (y=100) so
    # they bucket into separate rows. Within each row, authored out of order.
    rects = [
        (100, 10, 30, 30, COLORS[1]),  # top row, right
        (10, 10, 30, 30, COLORS[0]),   # top row, left
        (100, 100, 30, 30, COLORS[3]), # bottom row, right
        (10, 100, 30, 30, COLORS[2]),  # bottom row, left
    ]
    path = _sheet((180, 160), rects, tmp_path / "double.png")

    sprites = extract_sprites(path)

    assert len(sprites) == 4
    # Reading order: top row L->R, then bottom row L->R.
    assert [_dominant(s) for s in sprites] == [
        COLORS[0],
        COLORS[1],
        COLORS[2],
        COLORS[3],
    ]


def test_noise_blobs_filtered(tmp_path):
    # One real rect plus a tiny 3x3 speck; the speck is below the 5px minimum
    # and must be dropped.
    rects = [
        (40, 40, 40, 40, COLORS[0]),
        (5, 5, 3, 3, COLORS[1]),
    ]
    path = _sheet((120, 120), rects, tmp_path / "noise.png")

    sprites = extract_sprites(path)

    assert len(sprites) == 1
    assert _dominant(sprites[0]) == COLORS[0]
