---
id: no-graphics-import-test-needs-subprocess
root: gotchas
type: gotcha
status: current
summary: "Asserting a module doesn't import pygame/PIL via `sys.modules` fails in-process because tests/conftest.py imports pygame session-wide; run the import check in a fresh subprocess instead."
created: 2026-06-01
updated: 2026-06-01
---

# Testing "this module pulls in no graphics deps" needs a subprocess

`tests/conftest.py` imports `pygame` at module load (to force SDL dummy
drivers and stand up an off-screen display for the whole session). That means
by the time any test runs, `pygame` is already in `sys.modules`.

So a naive guard like:

```python
import twitch_playground.assets.character_defs
assert "pygame" not in sys.modules  # ALWAYS FALSE -- conftest already loaded it
```

gives a false failure -- it's measuring conftest's import, not the module under
test.

To actually verify a pure-data module (e.g. `character_defs.py`) imports no
graphics stack, import it in a fresh interpreter:

```python
code = (
    "import sys; import twitch_playground.assets.character_defs; "
    "assert 'pygame' not in sys.modules; assert 'PIL' not in sys.modules"
)
result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
assert result.returncode == 0, result.stderr
```

The clean subprocess has only what the target module's own import chain drags
in, so the assertion is meaningful.
