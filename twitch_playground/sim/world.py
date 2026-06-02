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
from twitch_playground.sim import personality
from twitch_playground.sim.character import Character, Mode, Neighbor
from twitch_playground.sim.personality import personality_for
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
            "panic": self._cmd_panic,
            "cheer": self._cmd_cheer,
        }.get(cmd.cmd)
        if handler:
            handler(cmd)

    def _cmd_join(self, cmd: ChatCommand) -> None:
        char = self.characters.get(cmd.author)
        if char is None:
            self.spawn(cmd.author)
            return
        char.touch()
        char.hold_autonomy()  # viewer intent wins; do not auto-rejoin right after
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
        a.hold_autonomy()
        b.hold_autonomy()

    def _cmd_follow(self, cmd: ChatCommand) -> None:
        if not cmd.args:
            return
        target = normalize_target(cmd.args[0])
        follower, leader = self.characters.get(cmd.author), self.characters.get(target)
        if follower is None or leader is None or follower is leader:
            return
        self._add_to_group(cmd.author, target)
        # Both ends were just placed by a viewer; hold off autonomy so the AI
        # does not immediately leave the cluster it was told to form.
        follower.hold_autonomy()
        leader.hold_autonomy()

    def _cmd_leave(self, cmd: ChatCommand) -> None:
        char = self.characters.get(cmd.author)
        if char is not None:
            char.hold_autonomy()  # do not auto-rejoin right after a manual leave
            self._remove_from_group(cmd.author)

    def _cmd_panic(self, cmd: ChatCommand) -> None:
        char = self._emotion_target(cmd)
        if char is not None:
            char.apply_emotion(
                d_valence=settings.PANIC_VALENCE_IMPULSE,
                d_arousal=settings.PANIC_AROUSAL_IMPULSE,
            )
            char.touch()

    def _cmd_cheer(self, cmd: ChatCommand) -> None:
        char = self._emotion_target(cmd)
        if char is not None:
            char.apply_emotion(
                d_valence=settings.CHEER_VALENCE_IMPULSE,
                d_arousal=settings.CHEER_AROUSAL_IMPULSE,
            )
            char.touch()

    def _emotion_target(self, cmd: ChatCommand) -> Character | None:
        """Resolve an emotion command's target: an explicit ``@name`` argument if
        given, else the command's own author. Contagion then ripples the impulse
        out to that character's neighbours over the next frames."""
        name = normalize_target(cmd.args[0]) if cmd.args else cmd.author
        return self.characters.get(name)

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
            persona=personality_for(username),
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
        # Build the shared neighbour records ONCE per frame -- a frame-start
        # snapshot (pos copied, plus heading and emotion) handed to every
        # character so all steering rules AND emotional contagion read one
        # consistent list rather than each re-scanning. This single record now
        # carries the L5 emotion fields too, so contagion adds no new query.
        neighbors = [
            Neighbor(
                Vector2(c.pos),
                c.facing,
                c.velocity.x,
                c.arousal,
                c.valence,
                c.expressiveness,
            )
            for c in self.characters.values()
        ]
        for char in self.characters.values():
            char.update(dt, neighbors, self.platforms)
        self._tick_autonomy(dt)

    # --- autonomous grouping (L4) ---------------------------------------------

    def _tick_autonomy(self, dt: float) -> None:
        """Run each character's low-frequency join/leave decision.

        Layered on top of the per-frame physics update above: the trait-biased
        utility check (sim/personality.py) decides, and the EXISTING grouping
        machinery (``_add_to_group`` / ``_remove_from_group``) executes -- no new
        Mode, no FSM rewrite. ``tick_autonomy`` gates the cadence, the manual
        hold, and the dwell clock; this method only acts when a decision is due.
        """
        if not settings.AUTONOMOUS_GROUPING:
            return
        # Snapshot the names: _add_to_group / _remove_from_group mutate group
        # membership (never the character set), so iterating a copy is safe.
        for username, char in list(self.characters.items()):
            if not char.tick_autonomy(dt):
                continue
            if char.mode is Mode.WANDER and char.platform is not None:
                if char._state_elapsed >= settings.LEAVE_DWELL:
                    self._consider_join(username, char)
            elif char.mode is Mode.GROUPED:
                if char._state_elapsed >= settings.JOIN_DWELL:
                    self._consider_leave(username, char)

    def _consider_join(self, username: str, char: Character) -> None:
        candidate = self._join_candidate(char)
        if candidate is None:
            return
        leader, distance, crowd_size = candidate
        if personality.join_score(char.persona, crowd_size, distance) >= settings.JOIN_ENTER_SCORE:
            self._add_to_group(username, leader)

    def _consider_leave(self, username: str, char: Character) -> None:
        if char.group_id is None:
            return
        members = self.groups.get(char.group_id, [])
        crowd_size = len(members)
        # Dual-threshold dead-band: only consider leaving once the cluster has
        # shrunk strictly below this character's join threshold, so the same size
        # that pulled it in does not immediately push it out.
        if crowd_size > personality.leave_floor(char.persona):
            return
        if personality.leave_score(char.persona, crowd_size, char._state_elapsed) >= settings.LEAVE_SCORE:
            self._remove_from_group(username)

    def _join_candidate(self, char: Character) -> tuple[str, float, int] | None:
        """Nearest reachable cluster for ``char``'s join check: ``(leader, distance,
        crowd_size)`` or None.

        Reachable = on the SAME surface (matching ``platform.top``), so the joiner
        can walk to the slot without a jump it cannot plan -- a cluster one tier up
        is not joinable and is skipped (else the character walks into a wall under
        an unreachable slot). ``crowd_size`` is the perceived knot: every same-
        surface character within ``JOIN_RADIUS``, so a cluster of wanderers can
        seed a new group, not just an already-formed one. The leader is the nearest
        such character's group anchor if it is grouped, else that character itself.
        """
        if char.platform is None:
            return None
        nearest: Character | None = None
        nearest_d: float | None = None
        crowd_size = 0
        for other in self.characters.values():
            if other is char or other.platform is None:
                continue
            if abs(other.platform.top - char.platform.top) > 1.0:
                continue  # different tier: not walk-reachable
            d = abs(other.pos.x - char.pos.x)
            if d > settings.JOIN_RADIUS:
                continue
            crowd_size += 1
            if nearest_d is None or d < nearest_d:
                nearest, nearest_d = other, d
        if nearest is None or nearest_d is None:
            return None
        if nearest.group_id is not None:
            leader = self.groups[nearest.group_id][0]  # join the cluster's anchor
        else:
            leader = nearest.username  # seed a new pair on the nearest wanderer
        return leader, nearest_d, crowd_size

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
