"""Sephirah character renderer -- `frieren run sephirah`.

Displays one of the five named Sephirah characters (Angela, Hod, Yesod,
Netzach, Malkuth) full-screen as a single pre-made portrait. The character is
driven by the same FastAPI server used by `frieren run robot`; clicking a voice
button in the control panel speaks the line AND shows that character here.

There is no sprite compositing: each portrait is a finished 256x256 RGBA image
shown scaled to fill the stage. While the engine is speaking the portrait gently
bobs (a small vertical sine plus a subtle breathing-scale pulse) so it reads as
"talking" without needing a separate mouth-open sprite. When silent it sits
still.

The speech balloon is reused from render.speech to stay consistent with the
existing robot renderer.
"""

from __future__ import annotations

import math
import os
import threading
import time

import pygame

from twitch_playground import settings
from twitch_playground.assets.sephirah_defs import SEPHIRAH_PORTRAITS
from twitch_playground.render import speech
from twitch_playground.robot import server

_BG = (21, 22, 26)
_STAGE_W = 600
_STAGE_H = 600
_INITIAL_SCALE = 1

# Portrait size as a fraction of the stage's smaller dimension (it fills most of
# the frame, leaving a little headroom for the bob and speech balloon).
_PORTRAIT_FRAC = 0.96

# Right-side volume slider (identical geometry to robot/renderer.py).
_SLIDER_STRIP_W = 56
_SLIDER_TRACK_W = 8
_SLIDER_MARGIN_Y = 48
_SLIDER_KNOB_R = 10
_SLIDER_PANEL = (28, 30, 36)
_SLIDER_TRACK_BG = (60, 64, 72)
_SLIDER_ACCENT = (224, 110, 96)


# ---------------------------------------------------------------------------
# Volume slider helpers (kept local so the two renderers are independent)
# ---------------------------------------------------------------------------

def _volume_track(win_w: int, win_h: int) -> tuple[int, int, int]:
    cx = win_w - _SLIDER_STRIP_W // 2
    return cx, _SLIDER_MARGIN_Y, max(_SLIDER_MARGIN_Y + 1, win_h - _SLIDER_MARGIN_Y)


def _volume_to_y(vol: float, top: int, bottom: int) -> int:
    return round(bottom - vol * (bottom - top))


def _y_to_volume(y: float, top: int, bottom: int) -> float:
    return max(0.0, min(1.0, (bottom - y) / (bottom - top)))


def _draw_volume(surf: pygame.Surface, font: pygame.font.Font, volume: float) -> None:
    win_w, win_h = surf.get_size()
    cx, top, bottom = _volume_track(win_w, win_h)
    pygame.draw.rect(surf, _SLIDER_PANEL, (win_w - _SLIDER_STRIP_W, 0, _SLIDER_STRIP_W, win_h))
    track = pygame.Rect(0, 0, _SLIDER_TRACK_W, bottom - top)
    track.center = (cx, (top + bottom) // 2)
    pygame.draw.rect(surf, _SLIDER_TRACK_BG, track, border_radius=_SLIDER_TRACK_W // 2)
    knob_y = _volume_to_y(volume, top, bottom)
    if bottom - knob_y > 0:
        fill = pygame.Rect(0, 0, _SLIDER_TRACK_W, bottom - knob_y)
        fill.midbottom = (cx, bottom)
        pygame.draw.rect(surf, _SLIDER_ACCENT, fill, border_radius=_SLIDER_TRACK_W // 2)
    pygame.draw.circle(surf, (240, 240, 244), (cx, knob_y), _SLIDER_KNOB_R)
    pygame.draw.circle(surf, _SLIDER_ACCENT, (cx, knob_y), _SLIDER_KNOB_R, 2)
    pct = font.render(f"{round(volume * 100)}%", True, (220, 220, 224))
    surf.blit(pct, pct.get_rect(center=(cx, top - 16)))
    cap = font.render("VOL", True, (150, 154, 162))
    surf.blit(cap, cap.get_rect(center=(cx, bottom + 16)))


# ---------------------------------------------------------------------------
# Portrait loading
# ---------------------------------------------------------------------------

class PortraitCache:
    """Lazily loads and caches one pygame Surface per character key.

    Must be used after pygame.display.set_mode() so convert_alpha() has an
    active video mode.
    """

    def __init__(self) -> None:
        self._cache: dict[str, pygame.Surface] = {}

    def get(self, key: str) -> pygame.Surface:
        if key not in self._cache:
            path = os.path.join(settings.SEPHIRAH_PORTRAITS_DIR, SEPHIRAH_PORTRAITS[key])
            self._cache[key] = pygame.image.load(path).convert_alpha()
        return self._cache[key]


# ---------------------------------------------------------------------------
# Server background thread
# ---------------------------------------------------------------------------

def _serve_in_background(host: str, port: int) -> None:
    import uvicorn
    uvicorn.Server(uvicorn.Config(server.app, host=host, port=port, log_level="warning")).run()


# ---------------------------------------------------------------------------
# Character resolution
# ---------------------------------------------------------------------------

def _resolve_char(name: str | None) -> str | None:
    """Map a voice/character name to a SEPHIRAH_PORTRAITS key, or None."""
    if name is None:
        return None
    key = name.lower()
    return key if key in SEPHIRAH_PORTRAITS else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    host = os.environ.get("ROBOT_HOST", "127.0.0.1")
    port = int(os.environ.get("ROBOT_PORT", "8080"))
    threading.Thread(
        target=_serve_in_background, args=(host, port), name="seph-server", daemon=True
    ).start()
    print(f"[sephirah] renderer up; control panel at http://{host}:{port}")

    pygame.init()
    settings.SCREEN_W, settings.SCREEN_H = _STAGE_W, _STAGE_H
    window = pygame.display.set_mode(
        (_STAGE_W * _INITIAL_SCALE + _SLIDER_STRIP_W, _STAGE_H * _INITIAL_SCALE),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption("Sephirah Renderer")
    clock = pygame.time.Clock()
    stage = pygame.Surface((_STAGE_W, _STAGE_H)).convert()
    font = pygame.font.SysFont(None, settings.SPEAK_FONT_SIZE)
    ui_font = pygame.font.SysFont(None, 22)

    speech.load_balloon()
    portraits = PortraitCache()

    # Pre-load all portraits in the background so the first utterance doesn't
    # stall on a cold load.
    def _warm() -> None:
        for key in SEPHIRAH_PORTRAITS:
            try:
                portraits.get(key)
            except Exception as exc:
                print(f"[sephirah] failed to pre-load {key!r}: {exc}")

    threading.Thread(target=_warm, name="seph-warm", daemon=True).start()

    base_size = max(1, round(min(_STAGE_W, _STAGE_H) * _PORTRAIT_FRAC))

    # The on-screen character persists: it is the server's current_face(), which
    # is seeded at startup and changes only on a color-change event. Once we have
    # resolved a valid portrait we keep showing it -- it never reverts to blank.
    displayed_key: str | None = None

    # Track when audio playback actually starts so the bob phase is continuous
    # from the first audible sample (synthesis time is silent -> no bob).
    play_started_at: float = 0.0
    was_playing: bool = False

    volume: float = 1.0
    pushed = None
    dragging = False

    running = True
    while running:
        clock.tick(settings.FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] >= window.get_size()[0] - _SLIDER_STRIP_W:
                    dragging = True
                    _, top, bottom = _volume_track(*window.get_size())
                    volume = _y_to_volume(event.pos[1], top, bottom)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                _, top, bottom = _volume_track(*window.get_size())
                volume = _y_to_volume(event.pos[1], top, bottom)

        # Volume push
        engine = server.STATE.engine
        if engine is not None and pushed != volume:
            engine.set_volume(volume)
            pushed = volume

        # Bob keys off ACTUAL audio playback, not synthesis. Record when playback
        # starts so the bob phase runs continuously from the first audible sample.
        is_playing = server.STATE.is_playing()
        if is_playing and not was_playing:
            play_started_at = time.monotonic()
        was_playing = is_playing

        # On-screen character: the persistent current_face(). Keep the last valid
        # portrait so the character never blinks out -- it only changes when a
        # color-change event moves current_face() to someone else.
        resolved = _resolve_char(server.current_face())
        if resolved is not None:
            displayed_key = resolved

        # Balloon text follows the active utterance; clear it once the engine is
        # done speaking. The character itself stays on screen regardless.
        if server.STATE.active is not None and not server.STATE.is_speaking():
            server.STATE.active = None
        active = server.STATE.active
        text = active[1] if active is not None else ""

        # Bob offset + scale pulse while audio is playing.
        bob_dy = 0
        scale_mul = 1.0
        if is_playing:
            phase = math.sin(2 * math.pi * settings.SPEAK_BOB_HZ * (time.monotonic() - play_started_at))
            bob_dy = round(phase * settings.SPEAK_BOB_AMPLITUDE * _STAGE_H)
            scale_mul = 1.0 + phase * settings.SPEAK_BOB_SCALE

        # Draw
        stage.fill(_BG)

        if displayed_key is not None:
            try:
                portrait = portraits.get(displayed_key)
                size = max(1, round(base_size * scale_mul))
                scaled = pygame.transform.smoothscale(portrait, (size, size))
                prect = scaled.get_rect(center=(_STAGE_W // 2, _STAGE_H // 2 + bob_dy))
                stage.blit(scaled, prect)

                if text.strip():
                    balloon = speech._build_balloon(text, font, text_color=(255, 255, 255))
                    brect = balloon.get_rect()
                    brect.midtop = (_STAGE_W // 2, 8)
                    brect.left = max(4, min(brect.left, _STAGE_W - brect.width - 4))
                    stage.blit(balloon, brect)
            except Exception as exc:
                label = font.render(f"[{displayed_key}]", True, (200, 200, 200))
                stage.blit(label, label.get_rect(center=(_STAGE_W // 2, _STAGE_H // 2)))
                if not getattr(_warn_sent, displayed_key, False):
                    print(f"[sephirah] failed to draw {displayed_key!r}: {exc}")
                    setattr(_warn_sent, displayed_key, True)

        # Scale stage into window viewport left of the slider strip.
        win_w, win_h = window.get_size()
        view_w = max(1, win_w - _SLIDER_STRIP_W)
        scale = min(view_w / _STAGE_W, win_h / _STAGE_H)
        dst = (round(_STAGE_W * scale), round(_STAGE_H * scale))
        window.fill((0, 0, 0))
        scaled_stage = pygame.transform.smoothscale(stage, dst)
        window.blit(scaled_stage, ((view_w - dst[0]) // 2, (win_h - dst[1]) // 2))
        _draw_volume(window, ui_font, volume)
        pygame.display.flip()

    pygame.quit()


class _WarnSent:
    """Namespace for per-character one-shot error flags."""


_warn_sent = _WarnSent()


if __name__ == "__main__":
    main()
