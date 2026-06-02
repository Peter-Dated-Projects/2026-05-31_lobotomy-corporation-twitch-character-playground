---
id: 0005-personality-skew-direction
root: decisions
type: decision
status: current
summary: "personality_for up-skews sociability (sqrt) and down-skews independence (square) so loners are a thin minority -- the inverse of the research brief's literal 'square the sociability draw', which down-skews and would make loners the majority; we followed the brief's stated intent over its example."
created: 2026-06-01
updated: 2026-06-01
---

# Personality skew direction (loners are a minority)

`sim/personality.personality_for` carves three uniform [0,1] draws from one md5
digest, then skews them:

- `sociability  = raw ** 0.5`  (sqrt -> **up**-skew, mean ~0.67: most are social)
- `independence = raw ** 2`    (square -> **down**-skew, mean ~0.33: contrarians rare)
- `restlessness = raw`         (uniform: cosmetic variety only)

## Why this, and why it contradicts the brief's example

`docs/research/crowd-following-personality.md` 2.1/2.4 states the *intent*
plainly: "skew the distribution so loners are a minority ... most characters are
mildly-to-strongly social and a tail is genuinely solitary," because the
threshold-model insight is that the distribution *shape* (not the mean) decides
whether crowds form at all.

But its concrete example -- "square the sociability draw" -- does the opposite of
that intent. For a uniform draw, `u**2` concentrates mass near 0, so squaring
*sociability* would make most characters **low**-social (loners the majority).

We followed the stated intent, not the example:
- Up-skew sociability with `sqrt` so most characters are social.
- Down-skew **independence** with `square`, because independence is what feeds the
  Granovetter join threshold `T = 1 + round(independence * MAX_JOIN_THRESHOLD)`.
  Squaring it means most characters get a low `T` (join readily, clusters
  nucleate) and only a thin tail are high-`T` true loners.

`tests/test_personality.py::test_distribution_is_skewed_so_loners_are_a_minority`
locks this in (mean sociability > 0.55, mean independence < 0.45, loner fraction
< 0.25). Do not "fix" the code back to literal `sociability ** 2` -- that would
invert the room and silently break crowd formation. See
[agent-behavior-model](../architecture/agent-behavior-model.md) L4 and
[0004-layered-agent-behavior](0004-layered-agent-behavior.md).
