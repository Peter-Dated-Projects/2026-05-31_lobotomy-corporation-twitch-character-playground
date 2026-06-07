"""Text-level profanity filter for the speak pipeline.

Runs on a viewer's Twitch chat message *before* it is handed to TTS. The goal
is to censor profanity that would otherwise be spoken aloud on stream. It is
pure Python, CPU-only, and sub-millisecond per message -- no ML, no model load.

Approach (see ``.charm/kb/swear-filter-research.md`` for the full research):
``better-profanity`` does the heavy lifting -- it ships a leetspeak
substitution map (``3``->``e``, ``@``->``a``, ``$``->``s``, ...) so ``h3ll``,
``f*ck`` and ``@ss`` are caught without custom code. We wrap it with a few
cheap normalization passes that close common evasion vectors the raw library
misses:

* **Unicode homoglyphs / full-width** -- NFKD normalize, then ASCII-fold so
  ``ＦＵＣＫ`` collapses to ``FUCK``.
* **Zalgo / combining diacritics** -- strip Unicode category ``Mn`` (nonspacing
  marks) after NFKD, which survive the ASCII fold otherwise.
* **Spaced-out letters** (``f u c k``) -- collapsed, but only when *every* token
  in the message is 1-2 chars, so normal sentences are left alone.
* **Interspersed separators** (``f.u.c.k``, ``f-u-c-k``) -- runs of single
  letters joined by a single punctuation char are de-separated before checking.

Because the censored output is what gets synthesized (not displayed back to the
viewer), it is fine that censoring a normalized form loses the original spacing
and case -- the spoken result is what matters.

Usage::

    from twitch_playground.speak.filter import filter_message
    clean = filter_message(viewer_message)   # -> profanity replaced with ****

Extend the wordlist with Twitch-specific slang at startup::

    from twitch_playground.speak.filter import add_censor_words
    add_censor_words(["somenewslur", "anotherone"])
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from better_profanity import profanity

# The censor wordlist is loaded exactly once (it is a non-trivial set build).
# better-profanity keeps it in module-global state, so we just guard the load.
_loaded = False

# Single spaces sitting between two word chars: "f u c k" but not leading/trailing.
_SPACED_LETTERS_RE = re.compile(r"(?<=\w)\s(?=\w)")

# Runs of single letters joined by one separator char each: f.u.c.k / f-u-c-k /
# f*u*c*k. Requires at least two "<letter><sep>" pairs plus a trailing letter,
# so "a-b" or "U.S." style two-token cases do NOT match -- kept deliberately
# conservative to avoid mangling normal punctuation.
_INTERSPERSED_RE = re.compile(r"\b(?:[a-zA-Z][.\-_*+]){2,}[a-zA-Z]\b")
_SEP_CHARS_RE = re.compile(r"[.\-_*+]")


def _ensure_loaded() -> None:
    """Load the default censor wordlist once, on first use."""
    global _loaded
    if not _loaded:
        profanity.load_censor_words()
        _loaded = True


def _strip_marks(text: str) -> str:
    """Drop Unicode nonspacing marks (category Mn) -- defuses zalgo/diacritics."""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _collapse_interspersed(text: str) -> str:
    """Collapse ``f.u.c.k`` / ``f-u-c-k`` runs into ``fuck`` before checking."""
    return _INTERSPERSED_RE.sub(lambda m: _SEP_CHARS_RE.sub("", m.group(0)), text)


def _normalize(text: str) -> str:
    """Fold homoglyphs/zalgo to ASCII and collapse spaced-out letters.

    1. NFKD decompose, then strip nonspacing marks (zalgo, combining accents).
    2. ASCII-fold (drops anything that did not decompose to ASCII).
    3. Collapse single-space-separated letters into one run, but only when the
       whole message is short tokens (all <=2 chars, more than 2 of them) so a
       normal sentence like "I am ok so go" is not mashed into one word.
    """
    text = unicodedata.normalize("NFKD", text)
    text = _strip_marks(text)
    text = text.encode("ascii", errors="ignore").decode("ascii")

    tokens = text.split()
    if len(tokens) > 2 and all(len(t) <= 2 for t in tokens):
        text = _SPACED_LETTERS_RE.sub("", text)
    return text


def filter_message(text: str) -> str:
    """Return ``text`` with profanity censored (each bad word -> ``****``).

    Checks several normalized views of the message and censors the first one
    that trips the filter; if none do, the original text is returned (passed
    through ``censor`` so any case better-profanity catches directly is still
    handled). The returned string is what should be sent to TTS.
    """
    _ensure_loaded()
    if not text:
        return text

    # Candidate views, in order of preference. The interspersed-collapse is run
    # before normalization so "ｆ.ｕ.ｃ.ｋ" style mixes are handled too.
    normalized = _normalize(text)
    de_interspersed = _normalize(_collapse_interspersed(text))

    for candidate in (normalized, de_interspersed):
        if profanity.contains_profanity(candidate):
            return profanity.censor(candidate)

    # Nothing tripped the normalized forms; still censor the original so any
    # in-place leetspeak/mixed-case profanity is replaced for readability.
    return profanity.censor(text)


def add_censor_words(words: Iterable[str]) -> None:
    """Extend the censor wordlist with extra terms (e.g. Twitch-specific slang).

    Safe to call at startup; ensures the default list is loaded first so the
    additions augment rather than replace it.
    """
    _ensure_loaded()
    profanity.add_censor_words(list(words))


__all__ = ["filter_message", "add_censor_words"]
