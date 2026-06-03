"""Entry point: owns the clock, the event loop, and the command-queue drain.

Run with:  uv run playground
The Twitch listener starts automatically if TWITCH_TOKEN/TWITCH_CHANNEL are set;
otherwise it runs in dev mode (keyboard injector only).
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
from twitch_playground.render import hud, scene
from twitch_playground.render.background import Background
from twitch_playground.sim.world import World


def main() -> None:
    load_dotenv()

    pygame.init()
    window = pygame.display.set_mode(
        (settings.SCREEN_W, settings.SCREEN_H), pygame.DOUBLEBUF | pygame.RESIZABLE
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
    world = World(make_provider())
    background = Background((settings.SCREEN_W, settings.SCREEN_H))
    command_queue: "queue.Queue[ChatCommand]" = queue.Queue()

    if start_chat_thread(command_queue) is not None:
        print("[main] Twitch listener started")
    else:
        print("[main] dev mode (no TWITCH_TOKEN/TWITCH_CHANNEL). " + HELP)

    injector = DevInjector(command_queue, lambda: list(world.characters))

    # rolling log of the most recently handled commands, shown by the HUD so
    # chat effects are visible while developing
    recent_commands: "deque[ChatCommand]" = deque(maxlen=hud.LOG_MAXLEN)
    hud_visible = True

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
            world.handle_command(cmd)

        world.update(dt)
        world.tick_despawn(time.monotonic())
        background.update(dt)
        background.draw(stage)  # owns the base fill; clears last frame
        scene.draw(stage, world)
        if hud_visible:
            hud.draw(stage, world, recent_commands)

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
