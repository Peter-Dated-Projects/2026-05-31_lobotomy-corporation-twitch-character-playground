"""LobCorpProvider sprite-cache keying.

The provider must cache one SpriteSet per RESOLVED character (CharacterDef
name), not per character_id (viewer username). Many usernames map to the same
look via assign_character, so keying by username would scale memory with the
viewer count for only ~10 real looks. These tests pin the keying invariant; they
hold whether or not the (repo-absent) real asset drop is present, since both the
composited and placeholder-fallback paths key by the resolved name.
"""

from __future__ import annotations

import pytest

from twitch_playground.assets.character_defs import CHARACTER_DEFS
from twitch_playground.assets.lobcorp_renderer import LobCorpProvider


@pytest.fixture
def lobcorp() -> LobCorpProvider:
    return LobCorpProvider()


def _usernames(n: int) -> list[str]:
    return [f"viewer_{i}" for i in range(n)]


def test_same_resolved_character_shares_one_sprite_set(lobcorp: LobCorpProvider) -> None:
    """Two distinct usernames that resolve to the same CharacterDef get the
    SAME cached SpriteSet object (shared, not rebuilt per username)."""
    # Find two usernames that resolve to the same character.
    by_resolved: dict[str, list[str]] = {}
    for name in _usernames(200):
        resolved = lobcorp._resolve(name).name
        by_resolved.setdefault(resolved, []).append(name)

    pair = next((names for names in by_resolved.values() if len(names) >= 2), None)
    assert pair is not None, "expected at least two usernames to collide on a character"
    a, b = pair[0], pair[1]

    assert lobcorp._resolve(a).name == lobcorp._resolve(b).name
    assert lobcorp.get_sprite_set(a) is lobcorp.get_sprite_set(b)


def test_cache_size_bounded_by_distinct_resolved_characters(
    lobcorp: LobCorpProvider,
) -> None:
    """Across many usernames the cache holds at most one entry per distinct
    resolved character -- never one per username."""
    names = _usernames(500)
    distinct_resolved = {lobcorp._resolve(n).name for n in names}

    for n in names:
        lobcorp.get_sprite_set(n)

    # One cache entry per distinct resolved character, keyed by that name.
    assert len(lobcorp._cache) == len(distinct_resolved)
    assert set(lobcorp._cache) == distinct_resolved
    # And, since there are only ~10 real looks, far fewer than the viewer count.
    assert len(lobcorp._cache) <= len(CHARACTER_DEFS)
    assert len(lobcorp._cache) < len(names)


def test_named_character_resolves_to_itself(lobcorp: LobCorpProvider) -> None:
    """A character_id that is already a CharacterDef name caches under that name
    (the named path bypasses assign_character)."""
    name = next(iter(CHARACTER_DEFS))
    lobcorp.get_sprite_set(name)
    assert name in lobcorp._cache
