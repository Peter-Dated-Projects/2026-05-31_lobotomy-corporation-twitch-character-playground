"""The sim brain: owns all characters, the follow-groups, and command handling.

Accessed only from the main thread (commands arrive via a thread-safe queue that
main drains here), so no locking is needed.
"""

from __future__ import annotations

import random
import time

import pygame
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import AssetProvider
from twitch_playground.chat.commands import ChatCommand, normalize_target
from twitch_playground.sim.character import Character
from twitch_playground.sim.platforms import default_level


class World:
    def __init__(self, provider: AssetProvider) -> None:
        self.provider = provider
        self.characters: dict[str, Character] = {}
        self.groups: dict[int, list[str]] = {}  # gid -> ordered members, [0] is anchor
        self._next_gid = 1
        self.platforms = default_level()  # index 0 is the full-width ground

        pygame.font.init()
        self._font = pygame.font.SysFont(None, settings.NAMEPLATE_FONT_SIZE)
        self._last_despawn_scan = time.monotonic()

    # --- command handling -----------------------------------------------------

    def handle_command(self, cmd: ChatCommand) -> None:
        handler = {
            "join": self._cmd_join,
            "hug": self._cmd_hug,
            "follow": self._cmd_follow,
            "leave": self._cmd_leave,
        }.get(cmd.cmd)
        if handler:
            handler(cmd)

    def _cmd_join(self, cmd: ChatCommand) -> None:
        char = self.characters.get(cmd.author)
        if char is None:
            self.spawn(cmd.author)
            return
        char.touch()
        if char.group_id is not None:  # re-joining pulls you out of a cluster
            self._remove_from_group(cmd.author)

    def _cmd_hug(self, cmd: ChatCommand) -> None:
        if not cmd.args:
            return
        target = normalize_target(cmd.args[0])
        a, b = self.characters.get(cmd.author), self.characters.get(target)
        if a is None or b is None or a is b:
            return  # join-required, target must exist, no self-hug
        a.trigger_hug()
        b.trigger_hug()

    def _cmd_follow(self, cmd: ChatCommand) -> None:
        if not cmd.args:
            return
        target = normalize_target(cmd.args[0])
        follower, leader = self.characters.get(cmd.author), self.characters.get(target)
        if follower is None or leader is None or follower is leader:
            return
        self._add_to_group(cmd.author, target)

    def _cmd_leave(self, cmd: ChatCommand) -> None:
        if cmd.author in self.characters:
            self._remove_from_group(cmd.author)

    # --- spawning / despawning ------------------------------------------------

    def spawn(self, username: str) -> Character:
        if len(self.characters) >= settings.MAX_CHARACTERS:
            self._evict_oldest(exclude=username)
        m = settings.WALL_MARGIN
        # spawn on the ground platform: feet at GROUND_TOP, random horizontal x
        pos = (random.uniform(m, settings.SCREEN_W - m), settings.GROUND_TOP)
        char = Character(
            username=username,
            pos=pos,
            sprites=self.provider.get_sprite_set(username),
            nameplate=self._build_nameplate(username),
        )
        self.characters[username] = char
        return char

    def _despawn(self, username: str) -> None:
        if username not in self.characters:
            return
        self._remove_from_group(username)
        self.characters.pop(username, None)

    def _evict_oldest(self, exclude: str) -> None:
        candidates = [(c.last_interaction, u) for u, c in self.characters.items() if u != exclude]
        if candidates:
            self._despawn(min(candidates)[1])

    def tick_despawn(self, now: float) -> None:
        if now - self._last_despawn_scan < settings.DESPAWN_SCAN_INTERVAL:
            return
        self._last_despawn_scan = now
        stale = [u for u, c in self.characters.items() if now - c.last_interaction > settings.IDLE_TIMEOUT]
        for u in stale:
            self._despawn(u)

    # --- grouping (follow clusters) ------------------------------------------

    def _add_to_group(self, follower: str, leader: str) -> None:
        self._remove_from_group(follower)  # leave any prior cluster first
        gid = self.characters[leader].group_id
        if gid is None:
            gid = self._next_gid
            self._next_gid += 1
            self.groups[gid] = [leader]
        if follower not in self.groups[gid]:
            self.groups[gid].append(follower)
        self._arrange_group(gid)

    def _remove_from_group(self, username: str) -> None:
        char = self.characters.get(username)
        if char is None or char.group_id is None:
            return
        gid = char.group_id
        members = self.groups.get(gid, [])
        if username in members:
            members.remove(username)
        char.set_wander()
        if len(members) <= 1:  # a one-member cluster dissolves
            for u in members:
                self.characters[u].set_wander()
            self.groups.pop(gid, None)
        else:
            self._arrange_group(gid)

    def _arrange_group(self, gid: int) -> None:
        """Anchor (members[0]) stays put; followers stand beside it on the
        leader's platform.

        Slots share the leader platform's surface y (`platform.top`) and fan out
        symmetrically in x, clamped to that platform's horizontal span so nobody
        is parked off the edge. If the leader is airborne (platform is None) we
        fall back to its current feet-y and the screen margins.
        """
        members = self.groups[gid]
        leader = self.characters[members[0]]
        anchor_pos = Vector2(leader.pos)
        spacing = settings.GROUP_SLOT_SPACING
        if leader.platform is not None:
            lo, hi = leader.platform.left, leader.platform.right
            slot_y = leader.platform.top
        else:
            m = settings.WALL_MARGIN
            lo, hi = m, settings.SCREEN_W - m
            slot_y = anchor_pos.y
        for i, username in enumerate(members):
            if i == 0:
                slot = Vector2(anchor_pos)  # anchor stays exactly where it is
            else:
                side = 1 if i % 2 == 1 else -1
                rank = (i + 1) // 2
                x = max(lo, min(hi, anchor_pos.x + side * rank * spacing))
                slot = Vector2(x, slot_y)
            self.characters[username].set_grouped(gid, slot)

    # --- per-frame ------------------------------------------------------------

    def update(self, dt: float) -> None:
        positions = [c.pos for c in self.characters.values()]
        for char in self.characters.values():
            char.update(dt, positions, self.platforms)

    # --- helpers --------------------------------------------------------------

    def _build_nameplate(self, username: str) -> pygame.Surface:
        outline = settings.NAMEPLATE_OUTLINE
        main = self._font.render(username, True, settings.NAMEPLATE_COLOR)
        w, h = main.get_size()
        plate = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            plate.blit(self._font.render(username, True, outline), (ox, oy))
        plate.blit(main, (1, 1))
        return plate
