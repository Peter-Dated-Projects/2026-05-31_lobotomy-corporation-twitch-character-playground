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

# The renderer draws to a fixed stage (matching the game's stage so the robot is
# scaled identically), then scales that up into a larger, resizable window.
_BG = (21, 22, 26)
_INITIAL_SCALE = 4


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
    stage_w, stage_h = settings.SCREEN_W, settings.SCREEN_H
    window = pygame.display.set_mode(
        (stage_w * _INITIAL_SCALE, stage_h * _INITIAL_SCALE), pygame.RESIZABLE
    )
    pygame.display.set_caption("Robot Renderer")
    clock = pygame.time.Clock()
    stage = pygame.Surface((stage_w, stage_h)).convert()
    font = pygame.font.SysFont(None, settings.SPEAK_FONT_SIZE)
    # Warm the sprite caches now that a video mode exists (convert_alpha needs it).
    speech.load_robot_sprites()
    speech.load_balloon()

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

        # Clear the overlay once the engine stops speaking (main-thread poll,
        # mirroring sim.world.tick_speak).
        if server.STATE.active is not None and not server.STATE.is_speaking():
            server.STATE.active = None

        stage.fill(_BG)
        active = server.STATE.active
        if active is not None:
            character, text = active
            speech.draw_speech(stage, character=character, text=text, font=font)

        # scale the stage into the (resizable) window, aspect-preserved + letterboxed
        win_w, win_h = window.get_size()
        scale = min(win_w / stage_w, win_h / stage_h)
        dst = (round(stage_w * scale), round(stage_h * scale))
        window.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(stage, dst)
        window.blit(scaled, ((win_w - dst[0]) // 2, (win_h - dst[1]) // 2))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
