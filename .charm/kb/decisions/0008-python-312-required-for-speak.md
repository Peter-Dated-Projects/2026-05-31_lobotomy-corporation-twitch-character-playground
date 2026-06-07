---
id: 0008-python-312-required-for-speak
root: decisions
type: decision
status: current
summary: "The speak feature forced requires-python from >=3.10 to >=3.12,<3.13 because kanade-tokenizer (KokoClone's voice-conversion model) hard-requires Python >=3.12; all pre-existing deps are 3.12-safe and the full test suite passes."
created: 2026-06-07
updated: 2026-06-07
---

`kanade-tokenizer` (the Kanade voice-conversion model behind KokoClone, the
chosen TTS engine -- see `tts-engine-decision.md`) declares `requires-python
>=3.12`. The repo was pinned `>=3.10,<3.11`, which made the speak feature
impossible to resolve. There is only one published kanade-tokenizer version
(0.1.0) and it has no 3.10/3.11 wheel, so there is no way to keep 3.10.

Decision: bump `requires-python` to `>=3.12,<3.13` (matching the verified
KokoClone spike, which ran on 3.12.5) in T-004, which owns `pyproject.toml`.

Why this is safe project-wide:
- All pre-existing deps (pygame-ce, twitchio<3, python-dotenv, Pillow, numpy,
  scipy) support 3.12.
- After `uv sync` recreated the shared `.venv` at 3.12, the full existing test
  suite (96 tests) still passes with no code changes.

Also required for the git dependency to install: set
`[tool.hatch.metadata] allow-direct-references = true` in pyproject, because
`kanade-tokenizer @ git+https://...` is a direct reference and hatchling rejects
those by default when building the project's own wheel.
