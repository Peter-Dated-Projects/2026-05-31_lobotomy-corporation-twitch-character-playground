#!/usr/bin/env python3
"""Build the Sephirah reference-voice MP3 library for the robot speak feature.

Downloads the English-dub character clips from the LoboCorpANV YouTube channel,
concatenates them per character, then TRIMS a short clean segment to use as the
voice-conversion reference. The engine (KokoClone -> Kanade VC) re-reads this
reference on every utterance, and a short clean clip (~15s of solo speech) is a
better VC target than a long clip that still carries background score/SFX.

Two files are written per character into twitch_playground/assets/voices/:
  - <name>.mp3       the trimmed reference the engine actually reads (~15s)
  - <name>.full.mp3  the full concatenated dub audio, kept for re-trimming

Trim region: a character listed in TRIM_REGIONS uses a hand-picked (start, end)
window verbatim -- preferred, since the heuristic below mis-picks on some clips.
Characters absent from TRIM_REGIONS fall back to the heuristic.

Trim heuristic (deterministic, no model): split the full clip into 0.5s frames,
compute each frame's RMS energy, mark a frame "voiced" when its RMS is above 40%
of the clip's 90th-percentile frame RMS, then slide a 15s window (skipping the
first ~5s of likely title music) in 0.5s steps and pick the window with the most
summed voiced energy. This favors a stretch of near-continuous speech over one
padded with pauses or quiet score. It is a heuristic, not VAD -- it picks the
loudest sustained-speech window, which on these dub clips is reliably speech.

The output directory is gitignored: these clips are derived from third-party
video and are machine-local, not vendored art.

Usage:
    uv run scripts/setup_voices.py                 # build every character
    uv run scripts/setup_voices.py --only hod      # just one
    uv run scripts/setup_voices.py --force         # rebuild existing MP3s
    uv run scripts/setup_voices.py --denoise        # run deepfilternet pass (optional)
    uv run scripts/setup_voices.py --list          # print the roster and exit

Requires `yt-dlp` and `ffmpeg` on PATH. `--denoise` additionally requires
`deepfilternet` (`uv add deepfilternet`); without it the flag is a no-op warning.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# Repo layout: this file lives at <repo>/scripts/setup_voices.py
REPO_ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = REPO_ROOT / "twitch_playground" / "assets" / "voices"

YOUTUBE_WATCH = "https://www.youtube.com/watch?v={id}"

# Target reference-clip audio format. 24kHz mono matches Kokoro's expected
# sample rate. VBR quality 2 (~190 kbps) is transparent and universally readable.
SAMPLE_RATE = 24000
MP3_QUALITY = "2"  # ffmpeg -q:a value; 0=best, 9=worst; 2 is ~190kbps VBR

# Trim parameters for picking the short VC reference out of the full dub audio.
TARGET_SECONDS = 15.0  # length of the trimmed reference clip
INTRO_SKIP_SECONDS = 5.0  # skip likely title music at the very start
FRAME_SECONDS = 0.5  # RMS analysis window
VOICED_FRACTION = 0.40  # frame is "voiced" if RMS > this * 90th-pct frame RMS

# Curated roster: only Sephirah with dedicated solo-speech clips on the channel.
# The "Day N" story videos are mixed narration and are intentionally excluded.
# Each value is the ordered list of YouTube video IDs concatenated into the
# reference WAV. Extend this dict as more clean clips are identified.
#
# Roster confirmed against https://www.youtube.com/@LoboCorpANV/videos on
# 2026-06-06. Chesed, Binah, Gebura, Tiphereth, and Hokma have no dedicated
# clip on the channel and are therefore not buildable from this source.
CHARACTERS: dict[str, list[str]] = {
    "hod": [
        "ZzaC8MsBPro",  # Hod 1
        "_CczzzR2IlI",  # Hod 2
        "wTydlsz6eDk",  # Hod 3
        "5qkY_p4FJ4M",  # Hod 4
        "wY7i3Zrs5Cw",  # hod_imaginary_technique
    ],
    "malkuth": [
        "qqRnCPcA9PY",  # Malkuth 1
        "2wU-tnNHkTw",  # Malkuth 2
        "HLkz2MXj2mk",  # Malkuth 3
        "7XscjetaVnI",  # Malkuth 4
        "dL16XHJ9nEk",  # malkuth_email
    ],
    "netzach": [
        "2h-Z1FX7whA",  # Netzach 1
        "SAi8HYy6QuE",  # Netzach 2
        "8OEibgEBR50",  # Netzach 3
        "Z3AdWfG0A-E",  # Netzach 4
    ],
    "yesod": [
        "ygtBSZ4WKUg",  # Yesod 1
        "z4b8dIH9VlE",  # Yesod 2
        "7tVR25jXj8M",  # Yesod 3
        "jVTv3rMzRBQ",  # Yesod 4
        "F8z1vath7-Y",  # yesod_from_lobotomies
    ],
}

# Hand-picked reference regions as (start_seconds, end_seconds) within each
# <name>.full.mp3, chosen by listening rather than trusting the energy heuristic.
# When a character appears here its region is used verbatim; otherwise the build
# falls back to _pick_clean_window. Re-derive these by cutting from the .full.mp3
# (which setup_voices keeps) and listening, then update the tuple here.
TRIM_REGIONS: dict[str, tuple[float, float]] = {
    "hod": (5.0, 35.0),
    "malkuth": (3.0, 23.0),
    "netzach": (15.0, 48.0),
    "yesod": (0.0, 30.0),
}


def _die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        _die(f"`{name}` not found on PATH. Install it and retry.")


def _run(cmd: list[str]) -> None:
    """Run a subprocess, surfacing stderr on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        _die(f"command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")


def _download_clip(video_id: str, dest_mp3: Path) -> None:
    """Download a single video's audio track as MP3."""
    # yt-dlp writes <out>.mp3; pass the stem and let it add the extension.
    _run(
        [
            "yt-dlp",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            MP3_QUALITY,
            "--no-playlist",
            "-o",
            str(dest_mp3.with_suffix("")) + ".%(ext)s",
            YOUTUBE_WATCH.format(id=video_id),
        ]
    )
    if not dest_mp3.exists():
        _die(f"expected {dest_mp3} after download but it is missing")


def _concat_and_normalize(clip_mp3s: list[Path], out_mp3: Path) -> None:
    """Concatenate clips and resample to the target reference format."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for m in clip_mp3s:
            # ffconcat needs single-quoted, escaped paths
            f.write(f"file '{m.as_posix()}'\n")
        list_file = Path(f.name)
    try:
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "-q:a",
                MP3_QUALITY,
                str(out_mp3),
            ]
        )
    finally:
        list_file.unlink(missing_ok=True)


def _pick_clean_window(full_mp3: Path) -> tuple[float, float]:
    """Pick the cleanest sustained-speech window in `full_mp3`.

    Returns (start_seconds, duration_seconds). See the module docstring for the
    heuristic. Deterministic: the same input always yields the same window.
    Falls back to a fixed offset if the clip is too short.
    """
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(full_mp3),
            "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "pipe:1",
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        return (INTRO_SKIP_SECONDS, TARGET_SECONDS)

    rate = SAMPLE_RATE
    samples = np.frombuffer(proc.stdout, dtype=np.int16)
    total_sec = len(samples) / rate
    if total_sec <= TARGET_SECONDS:
        return (0.0, total_sec)  # whole clip is shorter than the target window

    # Per-frame RMS energy over fixed FRAME_SECONDS windows.
    frame_len = max(1, int(rate * FRAME_SECONDS))
    n_frames = len(samples) // frame_len
    frames = samples[: n_frames * frame_len].astype(np.float64).reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(frames * frames, axis=1))

    # Relative "voiced" threshold: tracks speech loudness, robust to overall gain.
    voiced_threshold = VOICED_FRACTION * np.percentile(rms, 90)
    voiced_energy = np.where(rms >= voiced_threshold, rms, 0.0)

    # Slide a TARGET_SECONDS window in FRAME_SECONDS steps, skipping the intro,
    # and maximize summed voiced energy (a rolling sum over consecutive frames).
    window_frames = max(1, int(round(TARGET_SECONDS / FRAME_SECONDS)))
    if window_frames >= n_frames:
        return (0.0, total_sec)
    cumsum = np.concatenate(([0.0], np.cumsum(voiced_energy)))
    window_scores = cumsum[window_frames:] - cumsum[:-window_frames]

    intro_frames = int(round(INTRO_SKIP_SECONDS / FRAME_SECONDS))
    # Clamp the intro skip so a valid window always remains.
    intro_frames = min(intro_frames, len(window_scores) - 1)
    best = intro_frames + int(np.argmax(window_scores[intro_frames:]))
    return (best * FRAME_SECONDS, TARGET_SECONDS)


def _trim(full_mp3: Path, out_mp3: Path, start: float, dur: float) -> None:
    """Cut [start, start+dur] from full_mp3 into out_mp3 at the reference format."""
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{dur:.3f}",
            "-i",
            str(full_mp3),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-q:a",
            MP3_QUALITY,
            str(out_mp3),
        ]
    )


def _denoise(wav: Path) -> None:
    """Optional deepfilternet pass to strip background score/SFX in place."""
    try:
        import df  # noqa: F401
    except ImportError:
        print(
            "  warn: --denoise requested but `deepfilternet` is not installed; "
            "skipping. Run `uv add deepfilternet` to enable.",
            file=sys.stderr,
        )
        return
    _run([sys.executable, "-m", "df.enhance", str(wav), "-o", str(wav.parent)])


def build_character(name: str, video_ids: list[str], *, force: bool, denoise: bool) -> None:
    out_mp3 = VOICES_DIR / f"{name}.mp3"  # short trimmed reference the engine reads
    full_mp3 = VOICES_DIR / f"{name}.full.mp3"  # full concat, kept for re-trimming
    if out_mp3.exists() and not force:
        print(f"[{name}] exists, skipping (use --force to rebuild)")
        return

    print(f"[{name}] building from {len(video_ids)} clip(s)")
    with tempfile.TemporaryDirectory(prefix=f"voices_{name}_") as tmp:
        tmpdir = Path(tmp)
        clip_mp3s: list[Path] = []
        for i, vid in enumerate(video_ids):
            clip = tmpdir / f"{name}_{i:02d}.mp3"
            print(f"  download {vid} -> {clip.name}")
            _download_clip(vid, clip)
            clip_mp3s.append(clip)
        print(f"  concat + resample -> {full_mp3.name}")
        _concat_and_normalize(clip_mp3s, full_mp3)

    region = TRIM_REGIONS.get(name)
    if region is not None:
        start, end = region
        dur = end - start
        print(f"  trim hand-picked region {start:.0f}-{end:.0f}s -> {out_mp3.name}")
    else:
        start, dur = _pick_clean_window(full_mp3)
        print(f"  trim cleanest {dur:.0f}s window @ {start:.1f}s -> {out_mp3.name}")
    _trim(full_mp3, out_mp3, start, dur)

    if denoise:
        # Denoise the SHORT reference, not the 8-11min full clip.
        print(f"  denoise {out_mp3.name}")
        _denoise(out_mp3)
    print(f"[{name}] done -> {out_mp3} (full clip kept at {full_mp3.name})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="NAME", help="build only this character")
    parser.add_argument("--force", action="store_true", help="rebuild MP3s that already exist")
    parser.add_argument("--denoise", action="store_true", help="run deepfilternet pass (needs deepfilternet)")
    parser.add_argument("--list", action="store_true", help="print the roster and exit")
    args = parser.parse_args()

    if args.list:
        for name, ids in CHARACTERS.items():
            print(f"{name}: {len(ids)} clip(s) -> {[i for i in ids]}")
        return

    if args.only and args.only not in CHARACTERS:
        _die(f"unknown character '{args.only}'. Known: {', '.join(CHARACTERS)}")

    _require_tool("yt-dlp")
    _require_tool("ffmpeg")
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    roster = {args.only: CHARACTERS[args.only]} if args.only else CHARACTERS
    for name, video_ids in roster.items():
        build_character(name, video_ids, force=args.force, denoise=args.denoise)

    print(f"\nReference library at {VOICES_DIR}")


if __name__ == "__main__":
    main()
