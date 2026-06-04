"""Contract tests for the pure-data character definitions.

These run with no graphics stack: the module under test must not pull in
pygame or PIL, so the suite also asserts that importing it leaves those
modules unloaded.
"""

from __future__ import annotations

import subprocess
import sys

from twitch_playground.assets import character_defs as cd

EXPECTED_NAMES = {
    "Standard Agent",
    "Officer Chesed",
    "Officer Binah",
    "Officer Geburah",
    "Officer Netzach",
    "Officer Hod",
    "Officer Malkut",
    "Officer Yesod",
    "Panicked Worker",
    "Battle-Ready Agent",
}


def test_all_ten_characters_present_and_keyed_by_name():
    assert len(cd.CHARACTER_DEFS) == 10
    assert set(cd.CHARACTER_DEFS) == EXPECTED_NAMES
    # The dict key must equal the def's own name.
    for key, defn in cd.CHARACTER_DEFS.items():
        assert key == defn.name


def test_default_character_id_is_a_valid_key():
    assert cd.DEFAULT_CHARACTER_ID == "Standard Agent"
    assert cd.DEFAULT_CHARACTER_ID in cd.CHARACTER_DEFS


def test_every_face_dict_has_a_default_key():
    for defn in cd.CHARACTER_DEFS.values():
        assert "default" in defn.eyes, f"{defn.name} eyes missing default"
        assert "default" in defn.eyebrows, f"{defn.name} eyebrows missing default"
        assert "default" in defn.mouth, f"{defn.name} mouth missing default"


def test_face_layers_carry_full_resource_filenames():
    # Catches the abbreviated-prefix bug: every referenced sheet must be the
    # full on-disk name, not the table shorthand.
    for defn in cd.CHARACTER_DEFS.values():
        layers = [
            *defn.eyes.values(),
            *defn.eyebrows.values(),
            *defn.mouth.values(),
            defn.front_hair,
            defn.rear_hair,
        ]
        for layer in layers:
            assert layer.file.endswith(".png")
            assert "-resources.assets-" in layer.file
            assert layer.variant >= 0
        assert defn.clothes.endswith(".png")
        assert "-resources.assets-" in defn.clothes


def test_assign_character_is_deterministic_and_returns_valid_keys():
    sample = ["xqcOW", "pokimane", "shroud", "ninja", "", "a", "ZeroTwo_42", "用户名"]
    for username in sample:
        first = cd.assign_character(username)
        second = cd.assign_character(username)
        assert first == second, f"{username!r} mapping is not stable"
        assert first in cd.CHARACTER_DEFS


def test_assign_character_spreads_across_the_roster():
    # Not a uniformity guarantee -- just that the mapping isn't pinned to one
    # character, which would signal a broken hash/modulo.
    seen = {cd.assign_character(f"viewer_{i}") for i in range(200)}
    assert len(seen) > 1


def test_module_imports_without_pygame_or_pil():
    # Importing the data module must not drag in a graphics dependency. We
    # check in a fresh interpreter because the test session's conftest already
    # imports pygame, which would poison an in-process sys.modules check.
    code = (
        "import sys; import twitch_playground.assets.character_defs; "
        "assert 'pygame' not in sys.modules, 'character_defs imported pygame'; "
        "assert 'PIL' not in sys.modules, 'character_defs imported PIL'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
