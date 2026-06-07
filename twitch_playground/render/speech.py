"""Speak-event visual: a Sephirah robot body plus a speech balloon carrying the
(already-filtered) viewer message.

A pure rendering primitive. It owns no sim/speak state -- every dynamic value
(which character, what text, the font, where to anchor) arrives as a call
argument, and the only module-level state is the surface caches built once on
first use. The speak lifecycle and when/where to call this live in the wiring
ticket, not here.

Like the asset provider, the loaders call ``convert_alpha()`` and so must run
AFTER ``pygame.display.set_mode()``. Missing art degrades to a labeled
placeholder rather than crashing, matching the rest of the render path.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from twitch_playground import settings

_ROBOTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "robots"

# The four roster robots vendored under assets/robots/ (KB: robot-sprite-candidates).
ROSTER = ("hod", "malkuth", "netzach", "yesod")

# Robot body is scaled to a fraction of the stage height (the stage is a wide,
# short band, so height is the binding dimension). Kept as a fraction rather than
# a fixed px so the body tracks settings.SCREEN_H if the stage is resized.
_ROBOT_HEIGHT_FRAC = 0.85

# Speech balloon. balloon.png is a small (~101px) flat gray panel with a flat
# coral border and no tail (KB), so we 9-slice it to any size: the corners stay
# at native scale and only the straight edges/center stretch, keeping a uniform
# border at every balloon size. _BALLOON_BORDER is the native corner inset.
_BALLOON_BORDER = 8
_BALLOON_PAD = 6  # inner gap between the border and the text block
_BALLOON_GAP = 6  # vertical gap between the balloon's bottom and the robot's head
_BALLOON_MAX_W_FRAC = 0.6  # cap balloon width to this fraction of the stage width
_EDGE_MARGIN = 4  # keep the balloon this far inside the screen edges

_LINE_SPACING = 2  # extra px between wrapped text lines
_MAX_LINES = 4  # cap; overflow past this is ellipsized onto the last line
_TEXT_COLOR = (40, 40, 44)  # dark text on the balloon's light gray fill
_ELLIPSIS = "..."

# Fallback placeholder colors (only used if a robot/balloon PNG is missing).
_PLACEHOLDER_BODY = (96, 104, 120)
_PLACEHOLDER_FILL = (200, 200, 200)
_PLACEHOLDER_BORDER = (224, 110, 96)  # coral, matching the real balloon border

_robot_cache: dict[str, pygame.Surface] | None = None
_balloon_cache: pygame.Surface | None = None


# -- loaders ---------------------------------------------------------------
def load_robot_sprites() -> dict[str, pygame.Surface]:
    """Load, alpha-convert and downscale the four roster robot PNGs, keyed by
    roster name. Built once and cached. Must be called after display init."""
    global _robot_cache
    if _robot_cache is None:
        target_h = max(1, round(settings.SCREEN_H * _ROBOT_HEIGHT_FRAC))
        _robot_cache = {
            name: _load_robot(_ROBOTS_DIR / f"{name}.png", target_h) for name in ROSTER
        }
    return _robot_cache


def load_balloon() -> pygame.Surface:
    """Load and alpha-convert the speech-balloon PNG. Cached. Must be called
    after display init."""
    global _balloon_cache
    if _balloon_cache is None:
        try:
            _balloon_cache = pygame.image.load(str(_ROBOTS_DIR / "balloon.png")).convert_alpha()
        except (pygame.error, FileNotFoundError):
            _balloon_cache = _placeholder_balloon()
    return _balloon_cache


def _load_robot(path: Path, target_h: int) -> pygame.Surface:
    try:
        img = pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return _placeholder_robot(target_h)
    iw, ih = img.get_size()
    scale = target_h / ih
    return pygame.transform.smoothscale(img, (max(1, round(iw * scale)), target_h))


def _placeholder_robot(target_h: int) -> pygame.Surface:
    w = max(1, round(target_h * 0.5))
    surf = pygame.Surface((w, target_h), pygame.SRCALPHA).convert_alpha()
    pygame.draw.rect(surf, _PLACEHOLDER_BODY, surf.get_rect(), border_radius=w // 4)
    return surf


def _placeholder_balloon() -> pygame.Surface:
    """A flat gray panel with a coral border, mirroring the real balloon so the
    9-slice and color contract still hold if the asset is absent."""
    size = 2 * _BALLOON_BORDER + 1
    surf = pygame.Surface((size, size), pygame.SRCALPHA).convert_alpha()
    surf.fill(_PLACEHOLDER_FILL)
    pygame.draw.rect(surf, _PLACEHOLDER_BORDER, surf.get_rect(), _BALLOON_BORDER)
    return surf


# -- public draw -----------------------------------------------------------
def draw_speech(
    screen: pygame.Surface,
    *,
    character: str,
    text: str,
    font: pygame.font.Font,
    anchor: tuple[int, int] | None = None,
) -> None:
    """Draw the speak visual for ``character`` onto ``screen``.

    The robot body is drawn feet-anchored at ``anchor`` (midbottom, matching the
    scene's convention); ``anchor`` defaults to the bottom-center of the stage.
    A speech balloon holding the word-wrapped ``text`` is drawn above the robot's
    head, horizontally centered on it and clamped inside the screen edges. When
    ``text`` is blank only the robot body is drawn (no balloon) -- used to keep a
    persistent face on screen between utterances.
    """
    if anchor is None:
        anchor = (settings.SCREEN_W // 2, settings.SCREEN_H)
    ax, ay = anchor

    sprites = load_robot_sprites()
    robot = sprites.get(character)
    if robot is None:
        robot = _placeholder_robot(max(1, round(settings.SCREEN_H * _ROBOT_HEIGHT_FRAC)))

    robot_rect = robot.get_rect(midbottom=(ax, ay))
    screen.blit(robot, robot_rect)

    if not text.strip():
        return  # persistent face: robot only, no balloon

    balloon = _build_balloon(text, font)
    brect = balloon.get_rect()
    brect.midbottom = (robot_rect.centerx, robot_rect.top - _BALLOON_GAP)
    # keep the balloon fully on screen
    sw, sh = screen.get_size()
    brect.left = max(_EDGE_MARGIN, min(brect.left, sw - brect.width - _EDGE_MARGIN))
    brect.top = max(_EDGE_MARGIN, brect.top)
    screen.blit(balloon, brect)


# -- balloon construction --------------------------------------------------
def _build_balloon(text: str, font: pygame.font.Font) -> pygame.Surface:
    """Word-wrap ``text``, size a 9-sliced balloon to the wrapped block, and
    render the text inside its inner padding."""
    inset = _BALLOON_BORDER + _BALLOON_PAD
    max_inner_w = max(1, round(settings.SCREEN_W * _BALLOON_MAX_W_FRAC) - 2 * inset)
    lines = _wrap_text(text, font, max_inner_w)

    line_h = font.get_height()
    inner_w = max((font.size(line)[0] for line in lines), default=1)
    inner_h = line_h * len(lines) + _LINE_SPACING * (len(lines) - 1)

    balloon = _scale_balloon(load_balloon(), inner_w + 2 * inset, inner_h + 2 * inset)
    for i, line in enumerate(lines):
        label = font.render(line, True, _TEXT_COLOR)
        balloon.blit(label, (inset, inset + i * (line_h + _LINE_SPACING)))
    return balloon


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Greedy word wrap to ``max_width`` px. Words wider than ``max_width`` are
    hard-split mid-word. Lines past ``_MAX_LINES`` are dropped and the last kept
    line is ellipsized to signal the truncation."""
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            # a lone word still too wide is hard-split
            if not current and font.size(word)[0] > max_width:
                lines.extend(_split_long_word(word, font, max_width))
                current = lines.pop() if lines else ""
            else:
                current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    if len(lines) > _MAX_LINES:
        lines = lines[:_MAX_LINES]
        lines[-1] = _ellipsize(lines[-1], font, max_width)
    return lines


def _split_long_word(word: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Break a single word too wide to fit into chunks that each fit."""
    chunks: list[str] = []
    current = ""
    for ch in word:
        if font.size(current + ch)[0] <= max_width or not current:
            current += ch
        else:
            chunks.append(current)
            current = ch
    if current:
        chunks.append(current)
    return chunks


def _ellipsize(line: str, font: pygame.font.Font, max_width: int) -> str:
    """Trim ``line`` from the end until it plus an ellipsis fits ``max_width``."""
    if font.size(line + _ELLIPSIS)[0] <= max_width:
        return line + _ELLIPSIS
    while line and font.size(line + _ELLIPSIS)[0] > max_width:
        line = line[:-1]
    return (line + _ELLIPSIS) if line else _ELLIPSIS


def _scale_balloon(src: pygame.Surface, w: int, h: int) -> pygame.Surface:
    """9-slice ``src`` to ``w`` x ``h``: native-scale corners, edges stretched
    along their one axis, center stretched both ways. Keeps a uniform border at
    any size (the panel is a flat fill + flat border, so this reads as a crisp
    coral-bordered rect with no corner distortion)."""
    b = _BALLOON_BORDER
    w = max(w, 2 * b + 1)
    h = max(h, 2 * b + 1)
    sw, sh = src.get_size()
    # If the source is too small to slice, just stretch the whole thing.
    if sw < 2 * b + 1 or sh < 2 * b + 1:
        return pygame.transform.smoothscale(src, (w, h))

    dst = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
    # source bands: [0,b) corner, [b, sw-b) middle, [sw-b, sw) corner
    sx = (0, b, sw - b)
    sy = (0, b, sh - b)
    s_mid_w, s_mid_h = sw - 2 * b, sh - 2 * b
    # destination bands
    dx = (0, b, w - b)
    dy = (0, b, h - b)
    d_mid_w, d_mid_h = w - 2 * b, h - 2 * b

    src_w = (b, s_mid_w, b)
    src_h = (b, s_mid_h, b)
    dst_w = (b, d_mid_w, b)
    dst_h = (b, d_mid_h, b)

    for col in range(3):
        for row in range(3):
            piece = src.subsurface(pygame.Rect(sx[col], sy[row], src_w[col], src_h[row]))
            piece = pygame.transform.scale(piece, (dst_w[col], dst_h[row]))
            dst.blit(piece, (dx[col], dy[row]))
    return dst
