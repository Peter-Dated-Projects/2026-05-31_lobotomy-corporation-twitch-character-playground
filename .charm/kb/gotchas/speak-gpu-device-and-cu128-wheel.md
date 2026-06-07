---
id: speak-gpu-device-and-cu128-wheel
root: gotchas
type: gotcha
status: current
summary: "The speak engine picks CUDA->MPS->CPU and logs '[speak] device=<dev>'; plain PyPI torch is CPU-only on win/linux (RTF ~1.4, slower than real-time), so torch/torchaudio are pulled from the cu128 index for non-darwin while macOS stays on the default wheel. Set SPEAK_REQUIRE_GPU=1 to fail loud on CPU; SPEAK_DEVICE forces a backend."
created: 2026-06-07
updated: 2026-06-07
---

The speak pipeline (Kokoro synth + Kanade voice conversion) only runs faster
than real-time on a GPU. On CPU the RTF is ~1.4 (slower than real-time), and it
is easy to land on CPU without noticing because the default PyPI `torch` wheel
is CPU-only on Windows/Linux.

## Engine side (`twitch_playground/speak/_kokoclone.py`)

`KokoCloneCore.load()` resolves the device via `_resolve_device(torch, ...)`:

- Preference order: **CUDA -> MPS -> CPU**.
- `SPEAK_DEVICE` env (`cuda|mps|cpu|auto`, default `auto`) forces a backend; an
  explicit `cuda`/`mps` that is unavailable raises `SpeakUnavailableError`.
- `SPEAK_REQUIRE_GPU` env (truthy = 1/true/yes/on, default false): when set and
  the resolved device would be CPU, raises `SpeakUnavailableError("GPU required
  but none available; set SPEAK_REQUIRE_GPU=0 to allow CPU")`. When unset, CPU is
  allowed but a one-line WARNING is printed.
- The chosen device is always printed: `[speak] device=cuda|mps|cpu`.

MPS is untested for Kanade/Kokoro and torch's MPS backend has op-coverage gaps,
so the Kanade/vocoder load is wrapped: an MPS load failure falls back to CPU with
a warning (unless `SPEAK_REQUIRE_GPU` is set, which makes it raise instead). The
fallback covers model *load*; first-inference MPS failures are not separately
caught.

`_resolve_device` takes `torch` as an argument (not an import) so the selection
logic is import-free and unit-testable with a stub torch. The clear typed message
survives because `tts.py`'s `SpeakEngine.__init__` re-raises `SpeakUnavailableError`
as-is, *before* its generic `except Exception` that would otherwise re-wrap it as
"failed to load speak models".

## Dependency side (`pyproject.toml` + `uv.lock`)

The streaming PC's RTX 5070Ti is Blackwell (sm_120) and needs a CUDA 12.8+ build
(cu128). A platform-gated uv index handles this without breaking macOS dev:

```toml
[[tool.uv.index]]
name = "pytorch-cu128"
url = "https://download.pytorch.org/whl/cu128"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cu128", marker = "sys_platform != 'darwin'" }]
torchaudio = [{ index = "pytorch-cu128", marker = "sys_platform != 'darwin'" }]
```

Result in the lock: `sys_platform != 'darwin'` -> `torch 2.11.0+cu128` (the cu128
index tops out at 2.11.0, which satisfies `>=2.9`) with linux/win wheels + CUDA
deps; `sys_platform == 'darwin'` -> `torch 2.12.0` from PyPI (CPU/MPS). `uv lock`
and `uv sync` both verified succeeding on macOS. No CUDA wheels exist for macOS,
so do NOT drop the darwin marker.

GPU box manual (re)install one-liner if ever needed:

    uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

Related: [[espeak-data-path-length-limit]], [[voices-wav-is-trimmed-not-full]].
