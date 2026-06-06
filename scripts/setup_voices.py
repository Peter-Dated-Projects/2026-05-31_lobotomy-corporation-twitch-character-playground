#!/usr/bin/env python3
"""Build the Sephirah reference-voice WAV library for the robot speak feature.

Downloads the English-dub character clips from the LoboCorpANV YouTube channel,
concatenates the clips per character, and writes a single clean 24kHz mono WAV
per character to twitch_playground/assets/voices/<name>.wav. Those WAVs are the
reference audio that KokoClone's speaker encoder turns into a voice embedding at
startup (see .charm/kb/voice-cloning-research.md and sephirah-voices.md).

The output directory is gitignored: these clips are derived from third-party
video and are machine-local, not vendored art.

Usage:
    uv run scripts/setup_voices.py                 # build every character
    uv run scripts/setup_voices.py --only hod      # just one
    uv run scripts/setup_voices.py --force         # rebuild existing WAVs
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

# Repo layout: this file lives at <repo>/scripts/setup_voices.py
REPO_ROOT = Path(__file__).resolve().parent.parent
VOICES_DIR = REPO_ROOT / "twitch_playground" / "assets" / "voices"

YOUTUBE_WATCH = "https://www.youtube.com/watch?v={id}"

# Target reference-clip audio format. 24kHz mono matches Kokoro's expected
# sample rate; s16 keeps the files small and universally readable.
SAMPLE_RATE = 24000

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


def _download_clip(video_id: str, dest_wav: Path) -> None:
    """Download a single video's audio track as WAV."""
    # yt-dlp writes <out>.wav; pass the stem and let it add the extension.
    _run(
        [
            "yt-dlp",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "--no-playlist",
            "-o",
            str(dest_wav.with_suffix("")) + ".%(ext)s",
            YOUTUBE_WATCH.format(id=video_id),
        ]
    )
    if not dest_wav.exists():
        _die(f"expected {dest_wav} after download but it is missing")


def _concat_and_normalize(clip_wavs: list[Path], out_wav: Path) -> None:
    """Concatenate clips and resample to the target reference format."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for w in clip_wavs:
            # ffconcat needs single-quoted, escaped paths
            f.write(f"file '{w.as_posix()}'\n")
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
                "-sample_fmt",
                "s16",
                str(out_wav),
            ]
        )
    finally:
        list_file.unlink(missing_ok=True)


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
    out_wav = VOICES_DIR / f"{name}.wav"
    if out_wav.exists() and not force:
        print(f"[{name}] exists, skipping (use --force to rebuild)")
        return

    print(f"[{name}] building from {len(video_ids)} clip(s)")
    with tempfile.TemporaryDirectory(prefix=f"voices_{name}_") as tmp:
        tmpdir = Path(tmp)
        clip_wavs: list[Path] = []
        for i, vid in enumerate(video_ids):
            clip = tmpdir / f"{name}_{i:02d}.wav"
            print(f"  download {vid} -> {clip.name}")
            _download_clip(vid, clip)
            clip_wavs.append(clip)
        print(f"  concat + resample -> {out_wav.name}")
        _concat_and_normalize(clip_wavs, out_wav)

    if denoise:
        print(f"  denoise {out_wav.name}")
        _denoise(out_wav)
    print(f"[{name}] done -> {out_wav}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="NAME", help="build only this character")
    parser.add_argument("--force", action="store_true", help="rebuild WAVs that already exist")
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
