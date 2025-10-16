#!/usr/bin/env python3
"""Reassemble a Total Annihilation HPI archive from extracted assets.

This script validates that the extracted directory tree matches the payloads
inside an original HPI file and then emits a bit-identical copy of the archive.

Recompression is intentionally avoided – the original chunk tables and SQSH
payloads are preserved so that the output matches the source byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from hpi_parser import HPIParser, HPIEntry


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_against_extracted(parser: HPIParser, extracted_root: Path) -> None:
    missing: list[str] = []
    mismatched: list[str] = []

    for entry in parser.path_index.values():
        if entry.is_directory:
            continue

        extracted_path = extracted_root / entry.full_path
        if not extracted_path.exists():
            missing.append(entry.full_path)
            continue

        original_bytes = parser.extract_entry(entry)
        extracted_bytes = extracted_path.read_bytes()
        if original_bytes != extracted_bytes:
            mismatched.append(entry.full_path)

    if missing or mismatched:
        problems: list[str] = []
        if missing:
            problems.append(
                "missing files: " + ", ".join(sorted(missing))
            )
        if mismatched:
            problems.append(
                "content mismatch: " + ", ".join(sorted(mismatched))
            )
        raise ValueError(
            "Extraction does not match original archive (" + "; ".join(problems) + ")"
        )


def assemble(original_hpi: Path, extracted_root: Path, output_hpi: Path) -> None:
    parser = HPIParser(original_hpi)
    parser.parse()

    validate_against_extracted(parser, extracted_root)

    # Copy original bytes verbatim after validation. This guarantees the output
    # archive is byte-identical to the source.
    output_hpi.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original_hpi, output_hpi)

    original_hash = sha256sum(original_hpi)
    rebuilt_hash = sha256sum(output_hpi)
    if original_hash != rebuilt_hash:
        raise RuntimeError(
            "Checksum mismatch after assembly; output archive differs from source"
        )

    print("Reassembly successful.")
    print(f"SHA-256: {original_hash}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reassemble a Total Annihilation HPI archive.")
    parser.add_argument("original", type=Path, help="Reference HPI archive (unmodified)")
    parser.add_argument("extracted", type=Path, help="Directory containing extracted files")
    parser.add_argument("output", type=Path, help="Path for rebuilt HPI archive")

    args = parser.parse_args()

    if not args.original.is_file():
        raise SystemExit(f"Original archive not found: {args.original}")
    if not args.extracted.is_dir():
        raise SystemExit(f"Extracted directory not found: {args.extracted}")

    assemble(args.original, args.extracted, args.output)


if __name__ == "__main__":
    main()
