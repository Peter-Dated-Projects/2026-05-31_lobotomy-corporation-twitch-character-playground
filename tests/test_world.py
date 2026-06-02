"""Command acceptance: !follow, !hug, !leave, !join through World.

These reproduce the contract's Acceptance bullets headlessly. The ``calm``
fixture keeps wandering characters grounded so grouping geometry is stable.
"""

from __future__ import annotations

import pytest
from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import SpriteSet
from twitch_playground.chat.commands import ChatCommand
from twitch_playground.sim.character import Character, Mode
from twitch_playground.sim.personality import Personality
from twitch_playground.sim.world import World


@pytest.fixture
def no_autonomy(monkeypatch):
    """Disable the autonomous join/leave layer so a command test exercises only
    the command path -- otherwise the spawned characters' random personas could
    autonomously form or dissolve clusters and perturb the assertions."""
    monkeypatch.setattr(settings, "AUTONOMOUS_GROUPING", False)


class _RecordingProvider:
    """AssetProvider that records every character_id requested, so a test can
    assert World.spawn passes each viewer's own identity through. Delegates the
    actual SpriteSet to the placeholder provider -- no real assets needed."""

    def __init__(self, inner):
        self.inner = inner
        self.requested: list[str] = []

    def get_sprite_set(self, character_id: str) -> SpriteSet:
        self.requested.append(character_id)
        return self.inner.get_sprite_set(character_id)


def test_spawn_requests_each_viewers_own_character_id(provider):
    """Distinct viewers must request distinct character ids (their usernames),
    not a shared hardcoded type -- otherwise every viewer renders identically."""
    recorder = _RecordingProvider(provider)
    world = World(recorder)

    usernames = ["viewer1", "viewer2", "viewer3"]
    for u in usernames:
        world.spawn(u)

    assert recorder.requested == usernames


def test_update_builds_one_shared_neighbor_snapshot(provider, monkeypatch):
    """World.update builds the neighbour records ONCE per frame -- one list,
    handed to every character, carrying a frame-start (pos, facing, vx) snapshot
    decoupled from the live characters (the L3+ shared-plumbing contract)."""
    world = World(provider)
    a = world.spawn("a")
    b = world.spawn("b")
    a.pos = Vector2(100, settings.GROUND_TOP)
    b.pos = Vector2(140, settings.GROUND_TOP)
    a.velocity = Vector2(25, 0)
    b.velocity = Vector2(-15, 0)
    a._facing = 1
    b._facing = -1

    captured: dict[str, list] = {}

    def spy(self, dt, neighbors, platforms):  # noqa: ANN001 - test stub
        captured[self.username] = neighbors  # capture without mutating positions

    monkeypatch.setattr(Character, "update", spy)
    world.update(1 / 60)

    # Same list object handed to every character -- a single shared scan.
    assert captured["a"] is captured["b"]
    recs = captured["a"]
    assert len(recs) == 2

    by_x = {round(r.pos.x): r for r in recs}
    assert by_x[100].facing == 1 and by_x[100].vx == 25
    assert by_x[140].facing == -1 and by_x[140].vx == -15

    # The record snapshots pos, so a later character move does not rewrite it.
    a.pos.x = 999
    assert by_x[100].pos.x == 100


def _ground_two(world: World):
    """Spawn 'a' and 'b' and run one tick so both bind to the ground platform."""
    a = world.spawn("a")
    b = world.spawn("b")
    world.update(1 / 60)
    assert a.platform is not None and b.platform is not None
    return a, b


def test_follow_snaps_follower_beside_leader_anchor_stays_put(provider, calm, no_autonomy):
    world = World(provider)
    leader, follower = _ground_two(world)
    # Pin positions so the follower's walk-to-slot finishes in a bounded number
    # of frames (random spawn x can otherwise sit ~900px from the slot).
    leader.pos = Vector2(400, leader.pos.y)
    follower.pos = Vector2(470, follower.pos.y)
    leader_pos_before = Vector2(leader.pos)

    world.handle_command(ChatCommand(cmd="follow", args=["@a"], author="b"))

    # Same cluster, leader is the anchor.
    assert follower.group_id is not None
    assert leader.group_id == follower.group_id

    # Follower's slot is on the leader's platform, beside (not on top of) it.
    assert follower.group_slot is not None
    assert follower.group_slot.y == leader.platform.top
    assert leader.platform.left <= follower.group_slot.x <= leader.platform.right
    assert follower.group_slot.x != leader.pos.x

    # Anchor does not move when the cluster forms.
    assert leader.pos == leader_pos_before

    # And the follower actually walks onto the slot (grounded, not airborne).
    for _ in range(240):
        world.update(1 / 60)
    assert follower.platform is not None
    assert follower.pos.distance_to(follower.group_slot) <= 1.0
    assert leader.pos == leader_pos_before  # anchor still parked


def test_hug_reverts_both_and_does_not_freeze(provider, calm, no_autonomy):
    world = World(provider)
    a, b = _ground_two(world)

    world.handle_command(ChatCommand(cmd="hug", args=["@b"], author="a"))
    assert a.mode is Mode.EMOTING and b.mode is Mode.EMOTING
    assert a.clip == "hug" and b.clip == "hug"

    # Past HUG_DURATION both must resume prior behaviour, not stay frozen.
    for _ in range(120):  # 2s at dt=1/60
        world.update(1 / 60)
    assert a.mode is Mode.WANDER and b.mode is Mode.WANDER
    assert a.clip != "hug" and b.clip != "hug"


def test_leave_dissolves_a_one_member_cluster(provider, calm, no_autonomy):
    world = World(provider)
    a, b = _ground_two(world)
    world.handle_command(ChatCommand(cmd="follow", args=["@a"], author="b"))
    assert b.group_id is not None

    # b leaving drops the cluster to a single member, which must dissolve fully.
    world.handle_command(ChatCommand(cmd="leave", args=[], author="b"))
    assert b.group_id is None
    assert a.group_id is None
    assert world.groups == {}
    assert a.mode is Mode.WANDER and b.mode is Mode.WANDER


def test_rejoin_pulls_sender_out_of_a_cluster(provider, calm, no_autonomy):
    world = World(provider)
    a, b = _ground_two(world)
    world.handle_command(ChatCommand(cmd="follow", args=["@a"], author="b"))
    assert b.group_id is not None

    # !join while already grouped removes you from the cluster.
    world.handle_command(ChatCommand(cmd="join", args=[], author="b"))
    assert b.group_id is None
    assert b.mode is Mode.WANDER


# --- autonomous grouping (L4) -------------------------------------------------


def _freeze_wander(monkeypatch):
    """Pin the wander drift so test characters stay put within JOIN_RADIUS while
    the autonomous decision plays out."""
    monkeypatch.setattr(settings, "WANDER_DISPLACE", 0.0)
    monkeypatch.setattr(settings, "WANDER_REORIENT_CHANCE", 0.0)


def test_autonomous_join_forms_a_cluster(provider, calm, monkeypatch):
    """Two eager-joiner wanderers standing near each other autonomously gravitate
    into a cluster -- no chat command involved."""
    _freeze_wander(monkeypatch)
    world = World(provider)
    a, b = world.spawn("a"), world.spawn("b")
    # Same surface, ~40px apart: outside the separation radius (30), inside
    # JOIN_RADIUS (140), so they neither shove apart nor drift out of range.
    a.pos = Vector2(400, settings.GROUND_TOP)
    b.pos = Vector2(440, settings.GROUND_TOP)
    a._wander_heading = b._wander_heading = 0.0
    sociable = Personality(sociability=1.0, independence=0.0, restlessness=0.0)
    a.persona = b.persona = sociable
    a._decide_timer = b._decide_timer = 0.0

    for _ in range(300):  # 5s: clears LEAVE_DWELL, decisions fire
        world.update(1 / 60)

    assert world.groups, "an autonomous cluster should have formed"
    assert a.group_id is not None and b.group_id is not None
    assert a.group_id == b.group_id


def test_autonomous_leave_when_restless_loner_in_small_cluster(provider, calm, monkeypatch):
    """A restless contrarian stuck in a small cluster peels off on its own once
    the commit dwell has elapsed -- the symmetric leave check."""
    _freeze_wander(monkeypatch)
    world = World(provider)
    a, b = world.spawn("a"), world.spawn("b")
    a.pos = Vector2(400, settings.GROUND_TOP)
    b.pos = Vector2(440, settings.GROUND_TOP)
    world.update(1 / 60)  # ground both
    # Form the pair directly (NOT via a chat command, so no manual hold applies).
    world._add_to_group("b", "a")
    assert b.group_id is not None
    # b wants out; a is an unsociable non-mover that will neither leave nor re-pull
    # b back in (so the end-state assertion is not perturbed by a re-join).
    b.persona = Personality(sociability=0.0, independence=0.9, restlessness=1.0)
    a.persona = Personality(sociability=0.0, independence=1.0, restlessness=0.0)
    b._decide_timer = 0.0

    for _ in range(400):  # well past JOIN_DWELL (3s)
        world.update(1 / 60)

    assert b.group_id is None
    assert b.mode is Mode.WANDER


def test_chat_command_is_not_autonomously_undone(provider, calm, monkeypatch):
    """A viewer's !follow is authoritative: within the manual-hold window the
    autonomous leave check must not fire, even for a character that would
    otherwise bolt immediately."""
    _freeze_wander(monkeypatch)
    world = World(provider)
    a, b = world.spawn("a"), world.spawn("b")
    a.pos = Vector2(400, settings.GROUND_TOP)
    b.pos = Vector2(440, settings.GROUND_TOP)
    world.update(1 / 60)
    # b would love to leave on its own; a will not re-pull or leave.
    b.persona = Personality(sociability=0.0, independence=0.9, restlessness=1.0)
    a.persona = Personality(sociability=0.0, independence=1.0, restlessness=0.0)

    world.handle_command(ChatCommand(cmd="follow", args=["@a"], author="b"))
    assert b.group_id is not None

    held_frames = int((settings.MANUAL_HOLD_DURATION - 1.0) / (1 / 60))
    for _ in range(held_frames):  # ~7s, inside the 8s hold
        world.update(1 / 60)

    assert b.group_id is not None, "viewer's !follow was autonomously undone"
