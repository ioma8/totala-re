#!/usr/bin/env python3
"""
Total Annihilation HPI File Format Parser and extractor.

Implements directory parsing plus chunked SQSH (LZ77/zlib) decompression,
following the reverse engineered format of totala.exe.
"""

import argparse
import os
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

CHUNK_SIZE = 0x10000  # 64 KiB chunk size used by HPI files


class HPIHeader:
    """Represents the 20 byte HPI archive header."""

    def __init__(self, data: bytes):
        if len(data) < 20:
            raise ValueError("Header too small")

        self.magic = data[0:4]
        self.version = struct.unpack("<I", data[4:8])[0]
        self.file_size = struct.unpack("<I", data[8:12])[0]
        self.key = data[12]  # encryption key byte
        self.dir_offset_raw = struct.unpack("<I", data[16:20])[0]

        if self.key != 0:
            self.transformed_key = (((self.key >> 6) | (self.key << 2)) & 0xFF) ^ 0xFF
        else:
            self.transformed_key = 0

    def __repr__(self):
        return (
            f"HPIHeader(magic={self.magic}, version=0x{self.version:08x}, "
            f"size={self.file_size}, key=0x{self.key:02x}, "
            f"dir_offset=0x{self.dir_offset_raw:08x})"
        )


@dataclass
class HPIEntry:
    """Represents a file or directory entry inside the archive."""

    name: str
    full_path: str
    data_offset: int
    flags: int
    is_directory: bool
    is_compressed: bool
    size: Optional[int] = None
    chunk_table_offset: Optional[int] = None
    children: List["HPIEntry"] = field(default_factory=list)

    def __str__(self) -> str:
        kind = "DIR " if self.is_directory else "FILE"
        comp = " compressed" if self.is_compressed else ""
        return f"{kind} {self.full_path}{comp}"


def _to_buffer_offset(file_offset: int) -> int:
    """Convert file offset to decrypted buffer offset (header size is 0x14)."""
    return file_offset - 0x14


class HPIParser:
    """Core parser capable of listing and extracting HPI archives."""

    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)
        self.raw_data = self.filepath.read_bytes()
        self.header = HPIHeader(self.raw_data[0:20])
        self.decrypted_data = self._decrypt_data(self.raw_data[0x14:], self.header.transformed_key)
        self.root_entries: List[HPIEntry] = []
        self.path_index: Dict[str, HPIEntry] = {}

    @staticmethod
    def _decrypt_data(data: bytes, key: int, start_offset: int = 0x14) -> bytes:
        """Position-dependent XOR cipher (matches totala.exe)."""
        if key == 0:
            return bytes(data)

        decrypted = bytearray(len(data))
        for i, byte in enumerate(data):
            pos = (i + start_offset) & 0xFF
            decrypted[i] = pos ^ key ^ (~byte & 0xFF)
        return bytes(decrypted)

    def _read_u32(self, file_offset: int) -> int:
        idx = _to_buffer_offset(file_offset)
        return struct.unpack_from("<I", self.decrypted_data, idx)[0]

    def _read_cstring(self, file_offset: int) -> str:
        idx = _to_buffer_offset(file_offset)
        end = self.decrypted_data.find(b"\x00", idx)
        if end == -1:
            end = len(self.decrypted_data)
        return self.decrypted_data[idx:end].decode("ascii", errors="replace")

    def _parse_directory(self, file_offset: int, path: str = "") -> List[HPIEntry]:
        buffer_offset = _to_buffer_offset(file_offset)
        entry_count = struct.unpack_from("<I", self.decrypted_data, buffer_offset)[0]

        entries: List[HPIEntry] = []
        for i in range(entry_count):
            entry_offset = buffer_offset + 8 + i * 9
            name_offset, info_offset = struct.unpack_from("<II", self.decrypted_data, entry_offset)
            flags = self.decrypted_data[entry_offset + 8]

            name = self._read_cstring(name_offset)
            full_path = f"{path}/{name}" if path else name
            is_dir = bool(flags & 0x01)
            is_compressed = bool(flags & 0x02)

            entry = HPIEntry(
                name=name,
                full_path=full_path,
                data_offset=info_offset,
                flags=flags,
                is_directory=is_dir,
                is_compressed=is_compressed,
            )

            if is_dir:
                entry.children = self._parse_directory(info_offset, full_path)
            else:
                entry.size = self._read_u32(info_offset + 4)
                entry.chunk_table_offset = self._read_u32(info_offset)

            entries.append(entry)
            self.path_index[full_path.lower()] = entry
        return entries

    def parse(self) -> None:
        if self.header.magic != b"HAPI":
            raise ValueError(f"Invalid archive magic: {self.header.magic!r}")

        self.root_entries = self._parse_directory(self.header.dir_offset_raw)

    # ------------------------------------------------------------------ #
    # Listing helpers
    # ------------------------------------------------------------------ #
    def list_entries(self) -> None:
        """Print the directory tree."""
        def recurse(entry: HPIEntry, indent: int = 0) -> None:
            prefix = "  " * indent
            icon = "📁" if entry.is_directory else "📄"
            comp = " [COMP]" if entry.is_compressed else ""
            print(f"{prefix}{icon} {entry.name}{comp}")
            for child in entry.children:
                recurse(child, indent + 1)

        for entry in self.root_entries:
            recurse(entry)

    # ------------------------------------------------------------------ #
    # Extraction helpers
    # ------------------------------------------------------------------ #
    def extract_entry(self, entry: HPIEntry) -> bytes:
        if entry.is_directory:
            raise ValueError("Cannot extract directory; select a file entry.")
        if entry.size is None or entry.chunk_table_offset is None:
            raise ValueError("File entry lacks size or chunk metadata.")

        total_size = entry.size
        chunk_table_offset = entry.chunk_table_offset
        chunk_count = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        chunk_sizes = [
            self._read_u32(chunk_table_offset + i * 4) for i in range(chunk_count)
        ]

        chunk_data_offset = chunk_table_offset + 4 * chunk_count
        data = bytearray()
        current_offset = chunk_data_offset
        remaining = total_size

        for chunk_size in chunk_sizes:
            chunk_bytes = self._read_bytes(current_offset, chunk_size)
            chunk_data = self._decompress_sqsh_chunk(chunk_bytes)
            if remaining < len(chunk_data):
                data.extend(chunk_data[:remaining])
                remaining = 0
            else:
                data.extend(chunk_data)
                remaining -= len(chunk_data)
            current_offset += chunk_size
            if remaining <= 0:
                break

        return bytes(data[:total_size])

    def extract_to_path(self, entry: HPIEntry, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = self.extract_entry(entry)
        destination.write_bytes(data)

    def extract_all(self, destination: Path) -> None:
        for entry in self.path_index.values():
            if entry.is_directory:
                continue
            output_path = destination / entry.full_path
            self.extract_to_path(entry, output_path)

    # ------------------------------------------------------------------ #
    # Internal utilities
    # ------------------------------------------------------------------ #
    def _read_bytes(self, file_offset: int, length: int) -> bytes:
        idx = _to_buffer_offset(file_offset)
        return self.decrypted_data[idx : idx + length]

    @staticmethod
    def _decompress_sqsh_chunk(chunk: bytes) -> bytes:
        if len(chunk) < 19:
            raise ValueError("SQSH chunk too small")
        if chunk[:4] != b"SQSH":
            raise ValueError(f"Invalid SQSH magic: {chunk[:4]!r}")

        # Header layout: magic[4], unknown[1], compress[1], encrypt[1], comp_size[4], full_size[4], checksum[4]
        compression_type = chunk[5]
        encryption_flag = chunk[6]
        compressed_size = struct.unpack_from("<I", chunk, 7)[0]
        uncompressed_size = struct.unpack_from("<I", chunk, 11)[0]
        payload = bytearray(chunk[19 : 19 + compressed_size])

        if encryption_flag:
            for i in range(len(payload)):
                key_byte = i & 0xFF
                payload[i] = ((payload[i] - key_byte) ^ key_byte) & 0xFF

        if compression_type == 0:
            result = bytes(payload)
        elif compression_type == 1:
            result = HPIParser._decompress_lz77(payload, uncompressed_size)
        elif compression_type == 2:
            import zlib

            result = zlib.decompress(bytes(payload))
        else:
            raise ValueError(f"Unknown SQSH compression type: {compression_type}")

        return result[:uncompressed_size]

    @staticmethod
    def _decompress_lz77(src: bytes, expected_size: int) -> bytes:
        dbuf = bytearray(4096)
        w1 = 1
        w2 = 1
        in_pos = 0
        out = bytearray()

        if not src:
            return bytes(out)

        w3 = src[in_pos]
        in_pos += 1

        while len(out) < expected_size:
            if not (w2 & w3):
                if in_pos >= len(src):
                    break
                byte = src[in_pos]
                in_pos += 1
                out.append(byte)
                dbuf[w1] = byte
                w1 = (w1 + 1) & 0xFFF
            else:
                if in_pos + 1 >= len(src):
                    break
                count = src[in_pos] | (src[in_pos + 1] << 8)
                in_pos += 2
                dptr = count >> 4
                if dptr == 0:
                    break
                length = (count & 0x0F) + 2
                for _ in range(length):
                    byte = dbuf[dptr]
                    out.append(byte)
                    dbuf[w1] = byte
                    dptr = (dptr + 1) & 0xFFF
                    w1 = (w1 + 1) & 0xFFF
                    if len(out) >= expected_size:
                        break
            w2 <<= 1
            if w2 & 0x0100:
                w2 = 1
                if in_pos >= len(src):
                    break
                w3 = src[in_pos]
                in_pos += 1
            if in_pos >= len(src) and w2 != 1:
                # No more source bytes to refresh flags; enforce break
                if len(out) >= expected_size:
                    break

        return bytes(out[:expected_size])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Total Annihilation HPI archive parser.")
    parser.add_argument("archive", type=Path, help="Path to the .hpi archive.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the directory structure of the archive.",
    )
    parser.add_argument(
        "--extract",
        metavar=("ARCHIVE_PATH", "DEST"),
        nargs=2,
        help="Extract a single file to DEST.",
    )
    parser.add_argument(
        "--extract-all",
        metavar="DEST_DIR",
        help="Extract the entire archive to DEST_DIR.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    arg_parser = build_parser()
    args = arg_parser.parse_args(argv)

    parser = HPIParser(args.archive)
    parser.parse()

    if args.list:
        parser.list_entries()

    if args.extract:
        archive_path, dest = args.extract
        entry = parser.path_index.get(archive_path.lower())
        if entry is None:
            raise SystemExit(f"Path '{archive_path}' not found in archive.")
        parser.extract_to_path(entry, Path(dest))
        print(f"Extracted {archive_path} -> {dest}")

    if args.extract_all:
        dest_dir = Path(args.extract_all)
        for entry in parser.path_index.values():
            if entry.is_directory:
                continue
            destination = dest_dir / entry.full_path
            parser.extract_to_path(entry, destination)
        print(f"Extracted archive contents to {dest_dir}")

    if not any([args.list, args.extract, args.extract_all]):
        # Default behaviour: show quick stats
        total_files = sum(not e.is_directory for e in parser.path_index.values())
        total_dirs = sum(e.is_directory for e in parser.path_index.values())
        print(f"{parser.filepath.name}: {total_dirs} directories, {total_files} files")


if __name__ == "__main__":
    main()
