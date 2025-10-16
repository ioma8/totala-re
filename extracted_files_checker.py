#!/usr/bin/env python3
"""
Validation tool for decompressed Total Annihilation HPI exports.

Walks an extracted directory tree and performs lightweight sanity checks:
  - Verifies files exist and are non-empty.
  - Applies simple signature heuristics for common binary formats.
  - Confirms text-based resources decode as ASCII (with limited tolerance).

Reports a summary plus any anomalies encountered.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


TEXT_EXTENSIONS = {
    ".tdf",
    ".fbi",
    ".gui",
    ".ota",
    ".txt",
    ".cfg",
    ".ini",
    ".pl",
    ".lst",
    ".bos",
    ".ccx",
}

SIGNATURES: Dict[str, Sequence[bytes]] = {}

MAX_BINARY_SAMPLE = 16
MAX_TEXT_SAMPLE = 256
TEXT_REPLACEMENT_THRESHOLD = 0.30  # allow up to 30% replacement characters


@dataclass
class FileReport:
    path: Path
    issue: str


def is_text_file(ext: str) -> bool:
    return ext.lower() in TEXT_EXTENSIONS


def check_binary_signature(data: bytes, ext: str) -> Optional[str]:
    expected = SIGNATURES.get(ext.lower())
    sample = data[:MAX_BINARY_SAMPLE]
    if not expected:
        if sample and sample.count(0) == len(sample):
            return "suspicious leading zeros"
        return None
    if not any(sample.startswith(sig) for sig in expected):
        return f"unexpected signature: {sample!r}"
    return None


def check_text_payload(data: bytes) -> Optional[str]:
    try:
        decoded = data[:MAX_TEXT_SAMPLE].decode("ascii", errors="replace")
    except Exception as exc:  # pragma: no cover - defensive
        return f"text decode failed ({exc})"

    replacement_count = decoded.count("\ufffd")
    if replacement_count / max(1, len(decoded)) > TEXT_REPLACEMENT_THRESHOLD:
        return f"too many non-ascii characters ({replacement_count}/{len(decoded)})"
    return None


def scan_directory(root: Path) -> List[FileReport]:
    reports: List[FileReport] = []
    for file_path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            data = file_path.read_bytes()
        except Exception as exc:
            reports.append(FileReport(file_path, f"read error: {exc}"))
            continue

        if not data:
            reports.append(FileReport(file_path, "file is empty"))
            continue

        ext = file_path.suffix.lower()
        if is_text_file(ext):
            issue = check_text_payload(data)
            if issue:
                reports.append(FileReport(file_path, issue))
            continue

        issue = check_binary_signature(data, ext)
        if issue:
            reports.append(FileReport(file_path, issue))
    return reports


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate files extracted from Total Annihilation HPI archives."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Root directory containing extracted files.",
    )
    args = parser.parse_args(argv)

    root = args.directory
    if not root.is_dir():
        raise SystemExit(f"{root} is not a directory or cannot be accessed.")

    reports = scan_directory(root)
    total_files = sum(1 for _ in root.rglob("*") if _.is_file())

    if reports:
        print(f"[!] Detected {len(reports)} issues across {total_files} files:\n")
        for report in reports:
            print(f" - {report.path.relative_to(root)}: {report.issue}")
        print("\nRun completed with warnings.")
        sys.exit(1)

    print(f"All {total_files} files passed the basic sanity checks.")


if __name__ == "__main__":
    main()
