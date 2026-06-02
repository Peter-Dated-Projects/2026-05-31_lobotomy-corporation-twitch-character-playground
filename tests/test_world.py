"""Command acceptance: !follow, !hug, !leave, !join through World.

These reproduce the contract's Acceptance bullets headlessly. The ``calm``
fixture keeps wandering characters grounded so grouping geometry is stable.
"""

from __future__ import annotations

from pygame.math import Vector2

from twitch_playground import settings
from twitch_playground.assets.provider import SpriteSet
from twitch_playground.chat.commands import ChatCommand
from twitch_playground.sim.character import Character, Mode
from twitch_playground.sim.world import World


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


def test_follow_snaps_follower_beside_leader_anchor_stays_put(provider, calm):
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


def test_hug_reverts_both_and_does_not_freeze(provider, calm):
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


def test_leave_dissolves_a_one_member_cluster(provider, calm):
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


def test_rejoin_pulls_sender_out_of_a_cluster(provider, calm):
    world = World(provider)
    a, b = _ground_two(world)
    world.handle_command(ChatCommand(cmd="follow", args=["@a"], author="b"))
    assert b.group_id is not None

    # !join while already grouped removes you from the cluster.
    world.handle_command(ChatCommand(cmd="join", args=[], author="b"))
    assert b.group_id is None
    assert b.mode is Mode.WANDER
