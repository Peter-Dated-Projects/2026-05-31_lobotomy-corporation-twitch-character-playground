"""Robot renderer -- `frieren run robot`.

A minimal pygame window that draws ONLY the robot body + speech balloon (no
employee crowd, no sim), driven by the same backend the web control panel uses.
The FastAPI server runs on a background thread; this loop owns the main thread
(required for pygame/SDL on macOS) and each frame draws whoever the backend says
is speaking, clearing the overlay when playback ends.

Run it, then open the served control panel (printed on startup) in a browser:
clicking a button speaks the line AND shows that Sephirah's face here. Pair with
nothing else -- this single process is face + voice + buttons.
"""

from __future__ import annotations

import os
import threading

import pygame

from twitch_playground import settings
from twitch_playground.render import speech
from twitch_playground.robot import server

# The renderer draws to a fixed square stage (just the robot + balloon -- no wide
# employee band like the game), then scales it into a resizable window. The stage
# is square so the lone robot is centered with no wide letterbox dead space.
_BG = (21, 22, 26)
_STAGE_W = 500
_STAGE_H = 500
_INITIAL_SCALE = 1

# Volume slider on the right wall. A strip of this width is reserved at the right
# edge (the stage scales into the area left of it) and holds a vertical track the
# user drags to set playback gain 0->100%.
_SLIDER_STRIP_W = 56
_SLIDER_TRACK_W = 8
_SLIDER_MARGIN_Y = 48  # track inset from the top/bottom of the window
_SLIDER_KNOB_R = 10
_SLIDER_PANEL = (28, 30, 36)
_SLIDER_TRACK_BG = (60, 64, 72)
_SLIDER_ACCENT = (224, 110, 96)  # coral, matching the balloon border


def _volume_track(win_w: int, win_h: int) -> tuple[int, int, int]:
    """(center_x, track_top_y, track_bottom_y) of the vertical track, in window px."""
    cx = win_w - _SLIDER_STRIP_W // 2
    top = _SLIDER_MARGIN_Y
    bottom = max(top + 1, win_h - _SLIDER_MARGIN_Y)
    return cx, top, bottom


def _volume_to_y(vol: float, top: int, bottom: int) -> int:
    """Map a 0..1 volume to a y in the track (top = 100%, bottom = 0%)."""
    return round(bottom - vol * (bottom - top))


def _y_to_volume(y: float, top: int, bottom: int) -> float:
    """Inverse of :func:`_volume_to_y`, clamped to [0, 1]."""
    return max(0.0, min(1.0, (bottom - y) / (bottom - top)))


def _draw_volume(surf, font, volume: float) -> None:
    """Draw the right-wall volume strip: panel, track, filled level, knob, label."""
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


def _serve_in_background(host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(server.app, host=host, port=port, log_level="warning")
    uvicorn.Server(config).run()  # runs its own event loop on this thread


def main() -> None:
    host = os.environ.get("ROBOT_HOST", "127.0.0.1")
    port = int(os.environ.get("ROBOT_PORT", "8080"))
    threading.Thread(
        target=_serve_in_background, args=(host, port), name="robot-server", daemon=True
    ).start()
    print(f"[robot] renderer up; control panel at http://{host}:{port}")

    pygame.init()
    # Override the shared stage dimensions to a square BEFORE warming the sprite
    # caches: render.speech sizes/centers the robot from settings.SCREEN_W/H, so
    # this is what makes the robot fill a 500x500 square instead of the game's
    # wide 510x120 band. Safe here -- the renderer is its own process.
    settings.SCREEN_W, settings.SCREEN_H = _STAGE_W, _STAGE_H
    stage_w, stage_h = _STAGE_W, _STAGE_H
    # Open wide enough that the 500x500 stage renders at full scale AND the slider
    # strip fits beside it (so the robot view stays square, the strip is extra).
    window = pygame.display.set_mode(
        (stage_w * _INITIAL_SCALE + _SLIDER_STRIP_W, stage_h * _INITIAL_SCALE),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption("Robot Renderer")
    clock = pygame.time.Clock()
    stage = pygame.Surface((stage_w, stage_h)).convert()
    font = pygame.font.SysFont(None, settings.SPEAK_FONT_SIZE)
    ui_font = pygame.font.SysFont(None, 22)
    # Warm the sprite caches now that a video mode exists (convert_alpha needs it).
    speech.load_robot_sprites()
    speech.load_balloon()

    volume = 1.0       # authoritative playback gain; pushed to the engine below
    pushed = None      # last volume sent to the engine (re-pushed on change/ready)
    dragging = False   # True while the user holds the slider knob

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
                # A press anywhere in the right strip grabs the slider and jumps to it.
                if event.pos[0] >= window.get_size()[0] - _SLIDER_STRIP_W:
                    dragging = True
                    _, top, bottom = _volume_track(*window.get_size())
                    volume = _y_to_volume(event.pos[1], top, bottom)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                _, top, bottom = _volume_track(*window.get_size())
                volume = _y_to_volume(event.pos[1], top, bottom)

        # Push the volume to the engine once it exists and whenever it changes
        # (also covers the engine becoming ready after the user already dragged).
        engine = server.STATE.engine
        if engine is not None and pushed != volume:
            engine.set_volume(volume)
            pushed = volume

        # Clear the transient utterance (the balloon) once playback ends; the
        # persistent face below keeps the robot on screen between utterances.
        if server.STATE.active is not None and not server.STATE.is_speaking():
            server.STATE.active = None

        stage.fill(_BG)
        active = server.STATE.active
        if active is not None:
            character, text = active
            speech.draw_speech(stage, character=character, text=text, font=font)
        else:
            # No active utterance: keep the last speaker's robot on screen with no
            # balloon. None only before the very first utterance in random mode.
            face = server.current_face()
            if face is not None:
                speech.draw_speech(stage, character=face, text="", font=font)

        # Scale the stage into the window AREA LEFT OF the slider strip,
        # aspect-preserved + letterboxed; then draw the slider in the strip.
        win_w, win_h = window.get_size()
        view_w = max(1, win_w - _SLIDER_STRIP_W)
        scale = min(view_w / stage_w, win_h / stage_h)
        dst = (round(stage_w * scale), round(stage_h * scale))
        window.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(stage, dst)
        window.blit(scaled, ((view_w - dst[0]) // 2, (win_h - dst[1]) // 2))
        _draw_volume(window, ui_font, volume)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
