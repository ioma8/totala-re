#!/usr/bin/env python3
"""
Convert Total Annihilation TMH(F) sound assets into standard PCM WAV files.

Most SFX embedded in HPI archives carry a 64-byte proprietary header prefixed
with "TMH" (or "TMHF"). After this header the payload is raw 16-bit little-endian
PCM data, typically mono at ~22 kHz. This tool strips the custom header, writes
a standard RIFF/WAVE wrapper, and stores the result alongside the originals.
"""

from __future__ import annotations

import argparse
import wave
from pathlib import Path
from typing import Sequence

DEFAULT_SAMPLE_RATE = 22050  # Hz
TMH_HEADER_SIZE = 64


def detect_sample_rate(header: bytes) -> int:
    """
    Heuristic: sample rate appears to be stored at offset 0x14-0x15
    as a big-endian 16-bit integer (~0x55xx ≈ 21.8 kHz). Fall back to the
    default if the extracted value is out of a reasonable range.
    """
    if len(header) < 0x16:
        return DEFAULT_SAMPLE_RATE

    raw = int.from_bytes(header[0x14:0x16], "big")
    if 8_000 <= raw <= 48_000:
        return raw
    return DEFAULT_SAMPLE_RATE


def convert_file(path: Path, dest_root: Path) -> None:
    data = path.read_bytes()

    if data.startswith(b"RIFF"):
        target = dest_root / path.name
        target.write_bytes(data)
        return

    header = data[:TMH_HEADER_SIZE]
    payload = data[TMH_HEADER_SIZE:]
    if not payload:
        raise ValueError(f"No PCM payload detected in {path}")

    sample_rate = detect_sample_rate(header)
    nchannels = 1
    sampwidth = 2 if len(payload) % 2 == 0 else 1  # infer 16-bit vs 8-bit

    target = dest_root / (path.stem + ".wav")
    target.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(target.as_posix(), "wb") as wav:
        wav.setnchannels(nchannels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(sample_rate)
        wav.writeframes(payload)

    # Simple validation: reopen and read one frame.
    with wave.open(target.as_posix(), "rb") as wav:
        wav.readframes(1)


def convert_directory(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for wav_path in sorted(source.glob("*.WAV")):
        convert_file(wav_path, destination)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert Total Annihilation TMH(F) audio files to standard WAV."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Directory containing TMH(F) audio (e.g. extracted/sounds).",
    )
    parser.add_argument(
        "destination",
        type=Path,
        help="Output directory for converted WAV files.",
    )
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        raise SystemExit(f"{args.source} is not a directory.")

    convert_directory(args.source, args.destination)
    print(f"Converted audio written to {args.destination}")


if __name__ == "__main__":
    main()
