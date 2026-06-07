"""Tests for the speak-pipeline profanity filter.

Deterministic and fast: no model load, pure Python. Profanity is censored by
better-profanity to a run of ``*`` characters, so assertions check that the bad
word is gone and that censoring stars appear, rather than the exact star count.
"""

import pytest

from twitch_playground.speak.filter import add_censor_words, filter_message


def _is_censored(result: str, bad_word: str) -> bool:
    """True if the bad word is gone and a censoring star run is present."""
    return bad_word.lower() not in result.lower() and "*" in result


def test_clean_message_passes_through_unchanged():
    msg = "great play, that was a clutch round"
    assert filter_message(msg) == msg


def test_basic_profanity_is_censored():
    result = filter_message("you are a shit player")
    assert _is_censored(result, "shit")


@pytest.mark.parametrize(
    "raw, bad_word",
    [
        ("f*ck this", "fuck"),
        ("what an @ss", "ass"),
        ("h3ll no", "hell"),
    ],
)
def test_leetspeak_is_censored(raw, bad_word):
    result = filter_message(raw)
    assert _is_censored(result, bad_word)


def test_spaced_out_letters_are_censored():
    # Every token is 1-2 chars, so the spaced-letter collapse kicks in.
    result = filter_message("f u c k")
    assert "*" in result
    assert "f u c k" not in result


def test_dotted_insertion_is_censored():
    result = filter_message("f.u.c.k")
    assert _is_censored(result, "fuck")


def test_dashed_insertion_is_censored():
    result = filter_message("f-u-c-k")
    assert _is_censored(result, "fuck")


def test_fullwidth_homoglyph_is_censored():
    # Full-width latin letters; NFKD folds them to ASCII "FUCK".
    result = filter_message("ｆｕｃｋ you")
    assert "*" in result
    assert "ｆｕｃｋ" not in result


def test_false_positive_guard_short_words_not_mangled():
    # All tokens are 1-2 chars so the collapse heuristic activates internally,
    # but the collapsed form ("Iamoksogo") is not profane, so the original must
    # be returned untouched.
    msg = "I am ok so go"
    assert filter_message(msg) == msg


def test_add_censor_words_extends_wordlist():
    benign = "the kappa emote spammer"
    assert filter_message(benign) == benign
    add_censor_words(["kappa"])
    result = filter_message(benign)
    assert _is_censored(result, "kappa")


def test_empty_string_is_safe():
    assert filter_message("") == ""
