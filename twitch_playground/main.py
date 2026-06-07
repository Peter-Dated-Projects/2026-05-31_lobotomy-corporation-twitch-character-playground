"""Entry point: owns the clock, the event loop, and the command-queue drain.

Run with:  uv run playground
The Twitch listener starts automatically if TWITCH_ACCESS_TOKEN/TWITCH_CHANNEL are
set (the access token is validated and refreshed via TWITCH_REFRESH_TOKEN on
startup if it has expired); otherwise it runs in dev mode (keyboard injector only).
"""

from __future__ import annotations

import queue
import time
from collections import deque

import pygame
from dotenv import load_dotenv

from twitch_playground import settings
from twitch_playground.chat.bot import start_chat_thread
from twitch_playground.chat.commands import ChatCommand
from twitch_playground.dev import HELP, DevInjector, make_provider
from twitch_playground.render import hud, scene, speech
from twitch_playground.render.background import Background
from twitch_playground.sim.world import World


def _make_speak_engine():
    """Construct the speak TTS engine once at startup, degrading gracefully.

    Loading the engine pulls in the ML stack and its models (~25-30s), so it is
    opt-in via SPEAK_ENABLED. If the feature is disabled, the import fails (deps
    absent), or model/voice load fails, we log one clear line and return None --
    the app then runs normally with the speak feature inert (`!say` is a no-op).
    """
    if not settings.SPEAK_ENABLED:
        print("[main] speak feature disabled (set SPEAK_ENABLED=1 to enable)")
        return None
    try:
        from twitch_playground.speak.tts import SpeakEngine, SpeakEngineError
    except Exception as exc:  # optional deps not importable
        print(f"[main] speak feature unavailable (import failed): {exc}")
        return None
    try:
        engine = SpeakEngine(
            voices_dir=settings.SPEAK_VOICES_DIR, roster=settings.ROBOT_ROSTER
        )
    except SpeakEngineError as exc:
        print(f"[main] speak feature disabled (engine init failed): {exc}")
        return None
    print("[main] speak engine ready")
    return engine


def main() -> None:
    load_dotenv()

    pygame.init()
    window = pygame.display.set_mode(
        (settings.WINDOW_W, settings.WINDOW_H), pygame.DOUBLEBUF | pygame.RESIZABLE
    )
    pygame.display.set_caption(settings.CAPTION)
    clock = pygame.time.Clock()

    # The sim and scene draw against a fixed-size stage (the deliberate wide-short
    # 1920x200 capture band). The OS window is resizable; each frame the stage is
    # scaled to fit the current window, aspect-preserved with letterbox bars, so
    # all coordinate math stays in stage space and is untouched by resizing.
    stage = pygame.Surface((settings.SCREEN_W, settings.SCREEN_H)).convert()

    # provider and backdrop must be built after the display exists
    # (convert_alpha / image.load need a video mode)
    world = World(make_provider(), speak_engine=_make_speak_engine())
    background = Background((settings.SCREEN_W, settings.SCREEN_H))
    # Font for the speak balloon text (built once; reused every frame).
    speak_font = pygame.font.SysFont(None, settings.SPEAK_FONT_SIZE)
    command_queue: "queue.Queue[ChatCommand]" = queue.Queue()

    if start_chat_thread(command_queue) is not None:
        print("[main] Twitch listener started")
    else:
        print("[main] dev mode (no usable TWITCH_ACCESS_TOKEN/TWITCH_CHANNEL). " + HELP)

    injector = DevInjector(command_queue, lambda: list(world.characters))

    # rolling log of the most recently handled commands, shown by the HUD so
    # chat effects are visible while developing
    recent_commands: "deque[ChatCommand]" = deque(maxlen=hud.LOG_MAXLEN)
    hud_visible = True

    # transient on-screen notice (text, monotonic expiry) raised by a command
    # response -- e.g. the full-org "Organization not hiring." join denial
    notice: "tuple[str, float] | None" = None

    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                window = pygame.display.set_mode(
                    (event.w, event.h), pygame.DOUBLEBUF | pygame.RESIZABLE
                )
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_BACKQUOTE:
                    hud_visible = not hud_visible
                else:
                    injector.handle_key(event.key)

        while not command_queue.empty():
            try:
                cmd = command_queue.get_nowait()
            except queue.Empty:
                break
            recent_commands.append(cmd)
            response = world.handle_command(cmd)
            if response:
                notice = (response, time.monotonic() + hud.NOTICE_DURATION)

        world.update(dt)
        world.tick_despawn(time.monotonic())
        world.tick_speak()  # clear the speak overlay once playback finishes
        background.update(dt)
        background.draw(stage)  # owns the base fill; clears last frame
        scene.draw(stage, world)

        # Speak overlay: a robot body + speech balloon for the active utterance,
        # drawn over the scene (and under the debug HUD) for the duration of
        # playback. tick_speak() above clears active_speaker when audio ends.
        if world.active_speaker is not None:
            speech.draw_speech(
                stage,
                character=world.active_speaker.character,
                text=world.active_speaker.text,
                font=speak_font,
            )

        if hud_visible:
            hud.draw(stage, world, recent_commands)

        # transient notice (e.g. full-org denial): drawn regardless of the debug
        # HUD toggle since it is viewer-facing; clears itself when it expires
        if notice is not None:
            remaining = notice[1] - time.monotonic()
            if remaining <= 0:
                notice = None
            else:
                hud.draw_notice(stage, notice[0], remaining)

        # scale the fixed stage into the (possibly resized) window, preserving
        # aspect ratio; fill the leftover with letterbox bars
        win_w, win_h = window.get_size()
        scale = min(win_w / settings.SCREEN_W, win_h / settings.SCREEN_H)
        dst_w, dst_h = round(settings.SCREEN_W * scale), round(settings.SCREEN_H * scale)
        window.fill((0, 0, 0))
        scaled = pygame.transform.smoothscale(stage, (dst_w, dst_h))
        window.blit(scaled, ((win_w - dst_w) // 2, (win_h - dst_h) // 2))
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
