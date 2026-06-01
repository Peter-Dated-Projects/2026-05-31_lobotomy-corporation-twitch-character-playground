"""Debug overlay drawn on top of the scene.

Read-only window into the sim: viewer count, a per-character mode/clip label,
and a rolling log of the last few commands so chat effects are visible at a
glance while developing. This module never mutates the world -- it only reads
observable attributes (`world.characters`, each character's `mode`/`clip`/
`group_id`).

The main loop owns visibility (a toggle key) and the recent-command deque; this
module just renders whatever it is handed.
"""

from __future__ import annotations

from typing import Iterable

import pygame

from twitch_playground.chat.commands import ChatCommand

# How many recent commands the log shows. main.py sizes its deque from this so
# the two never drift.
LOG_MAXLEN = 6

# Max per-character rows before we collapse the tail into a "+N more" line, so a
# big crowd can't overflow the panel.
_MAX_ROSTER_ROWS = 16

_FONT_SIZE = 14
_LINE_H = 16
_PAD = 6
_MARGIN = 8

_TEXT_COLOR = (220, 230, 240)
_DIM_COLOR = (150, 160, 172)
_ACCENT_COLOR = (120, 210, 160)
_PANEL_COLOR = (12, 14, 18)
_PANEL_ALPHA = 165

# Fonts are built once on first draw (display/font subsystem must exist by then)
# and cached here -- rebuilding a SysFont every frame is needlessly expensive.
_fonts: dict[str, pygame.font.Font] = {}


def _get_fonts() -> tuple[pygame.font.Font, pygame.font.Font]:
    if not _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
        _fonts["regular"] = pygame.font.SysFont(None, _FONT_SIZE)
        bold = pygame.font.SysFont(None, _FONT_SIZE, bold=True)
        _fonts["bold"] = bold
    return _fonts["regular"], _fonts["bold"]


def draw(screen: pygame.Surface, world, recent_commands: Iterable[ChatCommand] | None = None) -> None:
    """Render the debug overlay onto `screen`. Call AFTER the scene is drawn."""
    regular, bold = _get_fonts()
    recent = list(recent_commands or ())

    _draw_roster(screen, world, regular, bold)
    _draw_command_log(screen, recent, regular, bold)


def _draw_roster(screen, world, regular, bold) -> None:
    characters = getattr(world, "characters", {})
    chars = list(characters.values())

    lines: list[tuple[str, tuple[int, int, int]]] = []
    lines.append((f"viewers: {len(chars)}", _ACCENT_COLOR))
    for char in chars[:_MAX_ROSTER_ROWS]:
        lines.append((_roster_line(char), _TEXT_COLOR))
    overflow = len(chars) - _MAX_ROSTER_ROWS
    if overflow > 0:
        lines.append((f"... +{overflow} more", _DIM_COLOR))

    _blit_panel(screen, lines, regular, bold, top_left=(_MARGIN, _MARGIN))


def _roster_line(char) -> str:
    name = getattr(char, "username", "?")
    mode = getattr(char, "mode", None)
    mode_label = getattr(mode, "name", str(mode)) if mode is not None else "?"
    clip = getattr(char, "clip", "?")
    gid = getattr(char, "group_id", None)
    group = f" g{gid}" if gid is not None else ""
    return f"{name}  {mode_label}/{clip}{group}"


def _draw_command_log(screen, recent: list[ChatCommand], regular, bold) -> None:
    lines: list[tuple[str, tuple[int, int, int]]] = [("commands", _ACCENT_COLOR)]
    if not recent:
        lines.append(("(none yet)", _DIM_COLOR))
    else:
        for cmd in recent:
            lines.append((_command_line(cmd), _TEXT_COLOR))

    panel_h = _PAD * 2 + _LINE_H * len(lines)
    top = screen.get_height() - _MARGIN - panel_h
    _blit_panel(screen, lines, regular, bold, top_left=(_MARGIN, top))


def _command_line(cmd: ChatCommand) -> str:
    args = " ".join(cmd.args) if getattr(cmd, "args", None) else ""
    head = f"!{cmd.cmd} {args}".rstrip()
    author = getattr(cmd, "author", "") or "?"
    return f"{head}  ({author})"


def _blit_panel(screen, lines, regular, bold, top_left) -> None:
    """Render `lines` (the first is treated as a bold header) inside a
    translucent panel anchored at `top_left`."""
    surfaces = []
    for i, (text, color) in enumerate(lines):
        font = bold if i == 0 else regular
        surfaces.append(font.render(text, True, color))

    width = max((s.get_width() for s in surfaces), default=0) + _PAD * 2
    height = _PAD * 2 + _LINE_H * len(surfaces)

    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill((*_PANEL_COLOR, _PANEL_ALPHA))
    for i, surf in enumerate(surfaces):
        panel.blit(surf, (_PAD, _PAD + i * _LINE_H))
    screen.blit(panel, top_left)
