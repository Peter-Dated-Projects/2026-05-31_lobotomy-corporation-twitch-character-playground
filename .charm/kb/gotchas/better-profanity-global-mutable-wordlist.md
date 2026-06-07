---
id: better-profanity-global-mutable-wordlist
root: gotchas
type: gotcha
status: current
summary: "better-profanity stores its censor wordlist in process-global state with no per-word removal; filter_message loads it once on first call and add_censor_words mutates it for the whole process, so wordlist edits leak across tests/modules."
created: 2026-06-07
updated: 2026-06-07
---

`twitch_playground/speak/filter.py` wraps `better_profanity.profanity`, whose
wordlist is module-global mutable state, not per-instance:

* `filter_message()` calls `profanity.load_censor_words()` once behind a module
  `_loaded` flag (loading the set is non-trivial; do not reload per message).
* `add_censor_words([...])` appends to that global set for the **entire
  process**. There is no clean per-word removal -- the only reset is
  `load_censor_words()`, which reloads the defaults and drops any additions.

Consequence: a test or startup hook that calls `add_censor_words(["kappa"])`
leaks that word into every later `filter_message()` call in the same process,
including other test files in a full `pytest` run. It is fine in practice when
the added terms are obscure enough not to collide with other tests' strings,
but if you need isolation, call `profanity.load_censor_words()` to restore
defaults rather than expecting the addition to be scoped.

The wiring ticket should call `add_censor_words()` exactly once at startup (not
per message), since the effect is permanent for the process anyway.
