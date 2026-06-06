# Swear-Word Filter Research: Python TTS Pipeline

Context: viewer Twitch chat message -> filter -> TTS synthesis -> audio playback. Filter runs text-level before TTS. Must be CPU-only, sub-50ms, Python-native.

---

## Recommendation

**Use `better-profanity` with a lightweight Unicode normalization pre-pass.**

This is the right call for this pipeline: pure Python, no ML, ~1ms latency, handles leetspeak and most common evasion patterns out of the box, and the wordlist is extensible.

### Install

```
uv add better-profanity
```

### Integration snippet

```python
import unicodedata
import re
from better_profanity import profanity

profanity.load_censor_words()  # call once at startup

_SPACE_RE = re.compile(r'(?<=\w)\s(?=\w)')  # single spaces between word chars

def _normalize(text: str) -> str:
    # strip Unicode homoglyphs to ASCII equivalents
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', errors='ignore').decode('ascii')
    # collapse spaced-out letters: "f u c k" -> "fuck"
    # only collapse runs where every token is 1-2 chars
    tokens = text.split()
    if all(len(t) <= 2 for t in tokens) and len(tokens) > 2:
        text = ''.join(tokens)
    return text

def filter_message(text: str) -> str:
    """Return text with profanity censored (replaced with ****)."""
    normalized = _normalize(text)
    # run filter on normalized form; if clean use original for readability
    if profanity.contains_profanity(normalized):
        return profanity.censor(normalized)
    return profanity.censor(text)  # also check original for mixed-case patterns
```

Notes on the snippet:
- `unicodedata.normalize('NFKD')` + ASCII encode collapses common homoglyphs (e.g. `ƒ` -> `f`, `а` Cyrillic-a -> dropped).
- The single-space collapsing heuristic (`"f u c k"` -> `"fuck"`) only activates when every token in the message is 1-2 chars, which avoids false-positives on normal sentences. For messages that mix short and long words, the raw text is still checked as a fallback.
- `better-profanity` internally applies a character substitution map for leetspeak (`3`->`e`, `0`->`o`, `@`->`a`, `$`->`s`, `1`->`i`, `!`->`i`, `5`->`s`, `7`->`t`). This catches `h3ll`, `f*ck`, `@ss`, etc. without custom code.

---

## Library Comparison

| Library | Evasion resistance | Latency (est.) | Install size | False-positive risk | Notes |
|---|---|---|---|---|---|
| **better-profanity** | Good (built-in leetspeak map, custom chars) | ~1ms | ~50KB (pure Python) | Low | Best fit for this use case |
| **profanity-filter** | Better (spaCy NLP pipeline) | 50-200ms | ~500MB with spaCy model | Medium | Too heavy; spaCy model load alone blows the latency budget |
| **alt-profanity-check** | Fair (Naive Bayes on Twitter corpus) | ~5-15ms | ~5MB | Medium-high | Occasional false positives on gaming slang; training corpus skews toward English social media |
| **Manual curated wordlist** | Depends entirely on maintenance | <1ms | Minimal | Lowest | Good as a supplement to better-profanity, not a replacement; brittle without active curation |

---

## Evasion Vectors NOT Covered

Even with normalization + better-profanity, these patterns can slip through:

1. **Unicode homoglyphs beyond ASCII range** -- e.g. full-width letters (`ｆｕｃｋ`), Cyrillic lookalikes (`с` = Cyrillic es). The NFKD normalization above handles many but not all. Mitigation: add `ftfy` or a homoglyph map if this becomes a problem in practice.

2. **Zalgo / combining diacritics** -- `f̴̨u̴̡c̵̡k̴` overlays combining chars that survive NFKD. Mitigation: strip Unicode category `Mn` (Mark, Nonspacing) after NFKD.

3. **Mid-word insertions of non-word chars** -- `f.u.c.k`, `f-u-c-k`. The space-collapsing heuristic doesn't catch these. Mitigation: add a pass that strips non-alphanumeric chars before filtering.

4. **Wordplay / context-dependent slurs** -- single-word innocent terms used as slurs in specific contexts. No text-level filter handles this without context.

5. **Newly coined / Twitch-specific slang** -- the default wordlist may lag community vocabulary. Mitigation: `profanity.add_censor_words(['slur1', 'slur2'])` at startup to extend the list.

---

## Post-TTS Audio-Level Filtering

Not worth it for this pipeline. The only viable CPU approach would be Whisper-tiny to re-transcribe the generated audio and then re-check the transcript -- but this adds 300-800ms latency on CPU, requires loading a second model, and is redundant with the text-level filter that already runs on the same content. The only scenario where audio-level filtering adds real value is when TTS itself could hallucinate profanity (not the case here; TTS is deterministic from the filtered text input). Skip it.
