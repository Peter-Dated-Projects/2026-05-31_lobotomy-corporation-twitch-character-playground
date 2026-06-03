"""Backdrop layer: a static control-room image plus a small drift of slowly
spinning, low-opacity white triangles rising up the stage.

Drawn FIRST, before platforms and characters -- this layer owns the base fill,
so the scene module no longer clears the surface itself. If the image asset is
missing the layer degrades to a flat ``settings.BG_COLOR`` fill, so the rest of
the render path never has to care whether art is present.

Cost budget: at most ``TRIANGLE_COUNT`` (50) triangles, each a tiny pre-rendered
surface rotated and blitted once per frame. The triangle geometry (rise / spin /
wrap) is pure and unit-tested without a display; only ``draw`` touches pygame
surfaces.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pygame

from twitch_playground import settings

_BG_IMAGE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "backgrounds" / "control_room.png"
)

# Ambient triangle drift. Kept deliberately sparse and translucent -- this is
# atmosphere behind the characters, not a focal element, and a hard count cap
# keeps the per-frame cost flat regardless of window size.
TRIANGLE_COUNT = 50
TRI_MIN_SIZE = 10
TRI_MAX_SIZE = 48
TRI_COLOR = (255, 255, 255)
TRI_ALPHA = 26  # low opacity so triangles read as a faint shimmer
TRI_RISE_MIN = 5.0  # px/sec upward
TRI_RISE_MAX = 20.0
TRI_SPIN_MIN = -22.0  # deg/sec; sign gives clockwise / counter-clockwise mix
TRI_SPIN_MAX = 22.0


@dataclass
class Triangle:
    """One drifting triangle in stage (canvas) coordinates. y grows downward, so
    rising means y decreases. Geometry only -- no pygame surface lives here, so
    this is trivially testable headless."""

    x: float
    y: float
    size: float
    angle: float  # current rotation in degrees
    spin: float  # deg/sec
    rise: float  # px/sec upward

    def step(self, dt: float) -> None:
        """Advance one frame: rise and rotate. Wrapping (respawn once fully off
        the top) is the Background's job since it needs the RNG and width."""
        self.y -= self.rise * dt
        self.angle = (self.angle + self.spin * dt) % 360.0

    def is_above_top(self) -> bool:
        """True once the triangle has fully cleared the top edge (y=0). ``size``
        is an upper bound on how far the shape extends from its anchor, so this
        is conservative -- the triangle is always fully gone before it wraps."""
        return self.y + self.size < 0


class Background:
    """Owns the cover-fit backdrop image and the ambient triangle field. Built
    with the stage size and draws straight onto the display surface at that size
    -- the backdrop is fitted to ``size`` once at construction, so ``draw`` is
    just blits with no per-frame scaling."""

    def __init__(self, size: tuple[int, int], *, rng: random.Random | None = None,
                 count: int = TRIANGLE_COUNT) -> None:
        self.rng = rng or random.Random()
        self.width, self.height = size
        self.image = self._load_image(size)
        self._base_cache: dict[int, pygame.Surface] = {}
        self.triangles = [self._spawn(initial=True) for _ in range(count)]

    # -- image -------------------------------------------------------------
    def _load_image(self, size: tuple[int, int]) -> pygame.Surface | None:
        """Load the backdrop and cover-fit it to ``size`` (scale to fill, then
        center-crop the overflow) so the 2.5:1 source art is not squashed into
        the wide 9.6:1 stage. Returns None if the asset is absent, leaving a
        flat-fill fallback."""
        try:
            img = pygame.image.load(str(_BG_IMAGE_PATH)).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None
        w, h = size
        iw, ih = img.get_size()
        scale = max(w / iw, h / ih)  # cover: fill both dimensions
        scaled = pygame.transform.smoothscale(img, (round(iw * scale), round(ih * scale)))
        crop = pygame.Rect(0, 0, w, h)
        crop.center = (scaled.get_width() // 2, scaled.get_height() // 2)
        return scaled.subsurface(crop).copy()

    # -- triangles ---------------------------------------------------------
    def _spawn(self, *, initial: bool) -> Triangle:
        """Make a triangle with randomized size / spin / rise. ``initial`` ones
        start scattered across the whole height (so the field is populated from
        frame one); respawns start just below the bottom edge and rise in."""
        size = self.rng.uniform(TRI_MIN_SIZE, TRI_MAX_SIZE)
        x = self.rng.uniform(0, self.width)
        y = self.rng.uniform(0, self.height) if initial else self.height + size
        return Triangle(
            x=x,
            y=y,
            size=size,
            angle=self.rng.uniform(0, 360),
            spin=self.rng.uniform(TRI_SPIN_MIN, TRI_SPIN_MAX),
            rise=self.rng.uniform(TRI_RISE_MIN, TRI_RISE_MAX),
        )

    def update(self, dt: float) -> None:
        for i, tri in enumerate(self.triangles):
            tri.step(dt)
            if tri.is_above_top():
                self.triangles[i] = self._spawn(initial=False)

    def _base_surface(self, size: int) -> pygame.Surface:
        """An upward-pointing translucent-white triangle on a transparent square,
        cached per integer size so we rotate-and-blit rather than re-rasterize."""
        surf = self._base_cache.get(size)
        if surf is None:
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.polygon(
                surf,
                (*TRI_COLOR, TRI_ALPHA),
                [(size / 2, 0), (0, size), (size, size)],
            )
            self._base_cache[size] = surf
        return surf

    # -- render ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if self.image is not None:
            surface.blit(self.image, (0, 0))
        else:
            surface.fill(settings.BG_COLOR)
        for tri in self.triangles:
            base = self._base_surface(int(tri.size))
            rotated = pygame.transform.rotate(base, tri.angle)
            rect = rotated.get_rect(center=(int(tri.x), int(tri.y)))
            surface.blit(rotated, rect)
