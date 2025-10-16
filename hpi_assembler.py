#!/usr/bin/env python3
"""Reassemble a Total Annihilation HPI archive from extracted assets.

This script builds a proper HPI archive from an extracted directory tree,
implementing the exact reverse operations of hpi_parser.py.

It compresses files using SQSH chunks, builds directory structures,
encrypts the data, and validates checksums at the end.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

CHUNK_SIZE = 0x10000  # 64 KiB chunk size used by HPI files


@dataclass
class FileEntry:
    """Represents a file to be added to the archive."""
    name: str
    full_path: str
    local_path: Path
    data: bytes = field(repr=False)
    chunk_table_offset: int = 0
    uncompressed_size: int = 0


@dataclass
class DirEntry:
    """Represents a directory in the archive."""
    name: str
    full_path: str
    subdirs: List[DirEntry] = field(default_factory=list)
    files: List[FileEntry] = field(default_factory=list)


class HPIAssembler:
    """Assembles HPI archives from extracted directory trees."""

    def __init__(self, extracted_root: Path, compression_mode: int = 2, encryption_key: int = 0):
        self.extracted_root = Path(extracted_root)
        self.compression_mode = compression_mode  # 0=none, 1=LZ77, 2=zlib
        self.encryption_key = encryption_key
        self.root_dir = DirEntry(name="", full_path="")
        
        # Build transformed key for encryption
        if self.encryption_key != 0:
            self.transformed_key = (((self.encryption_key >> 6) | (self.encryption_key << 2)) & 0xFF) ^ 0xFF
        else:
            self.transformed_key = 0

        # Buffer to hold the encrypted portion of the archive
        self.buffer = bytearray()
        
        # Offset tracking
        self.current_offset = 0x14  # Start after 20-byte header

    def scan_directory_tree(self) -> None:
        """Scan the extracted directory and build internal structure."""
        if not self.extracted_root.exists():
            raise ValueError(f"Extracted root does not exist: {self.extracted_root}")
        
        self._scan_dir(self.extracted_root, self.root_dir)

    def _scan_dir(self, fs_path: Path, dir_entry: DirEntry) -> None:
        """Recursively scan filesystem directory."""
        if not fs_path.is_dir():
            return
        
        items = sorted(fs_path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        
        for item in items:
            if item.is_dir():
                subdir_name = item.name
                subdir_full_path = f"{dir_entry.full_path}/{subdir_name}" if dir_entry.full_path else subdir_name
                subdir_entry = DirEntry(name=subdir_name, full_path=subdir_full_path)
                dir_entry.subdirs.append(subdir_entry)
                self._scan_dir(item, subdir_entry)
            elif item.is_file():
                file_name = item.name
                file_full_path = f"{dir_entry.full_path}/{file_name}" if dir_entry.full_path else file_name
                file_data = item.read_bytes()
                file_entry = FileEntry(
                    name=file_name,
                    full_path=file_full_path,
                    local_path=item,
                    data=file_data
                )
                dir_entry.files.append(file_entry)

    def assemble(self, output_path: Path) -> None:
        """Main assembly routine."""
        self.scan_directory_tree()
        
        # Build the directory tree and file payloads
        dir_offset = self._build_archive_data()
        
        # Write the header
        header = self._build_header(dir_offset)
        
        # Encrypt the buffer
        encrypted_buffer = self._encrypt_data(bytes(self.buffer), self.transformed_key)
        
        # Write final archive
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            f.write(header)
            f.write(encrypted_buffer)
        
        print(f"Archive assembled successfully: {output_path}")
        print(f"Total size: {len(header) + len(encrypted_buffer)} bytes")

    def _build_header(self, dir_offset: int) -> bytes:
        """Build the 20-byte HPI header."""
        # Calculate total file size
        total_size = 0x14 + len(self.buffer)
        
        header = bytearray(20)
        header[0:4] = b"HAPI"  # magic
        struct.pack_into("<I", header, 4, 0x00010000)  # version
        struct.pack_into("<I", header, 8, total_size)  # file_size
        header[12] = self.encryption_key  # key byte
        struct.pack_into("<I", header, 16, dir_offset)  # dir_offset
        
        return bytes(header)

    def _encrypt_data(self, data: bytes, key: int) -> bytes:
        """Position-dependent XOR cipher (matches totala.exe)."""
        if key == 0:
            return data
        
        encrypted = bytearray(len(data))
        for i, byte in enumerate(data):
            pos = (i + 0x14) & 0xFF
            encrypted[i] = (~(pos ^ key ^ byte)) & 0xFF
        return bytes(encrypted)

    def _build_archive_data(self) -> int:
        """Build all archive data structures and return directory offset."""
        # First pass: write all file payloads and build chunk tables
        self._write_file_payloads(self.root_dir)
        
        # Second pass: write all directory structures
        dir_offset = self._write_directory_tree(self.root_dir)
        
        return dir_offset

    def _write_file_payloads(self, dir_entry: DirEntry) -> None:
        """Write compressed file data for all files in directory tree."""
        for file_entry in dir_entry.files:
            file_entry.chunk_table_offset = self._write_compressed_file(file_entry.data)
            file_entry.uncompressed_size = len(file_entry.data)
        
        for subdir in dir_entry.subdirs:
            self._write_file_payloads(subdir)

    def _write_compressed_file(self, data: bytes) -> int:
        """Write compressed file data and return chunk table offset."""
        chunk_count = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunk_table_offset = self.current_offset
        
        # Reserve space for chunk table
        chunk_table_size = chunk_count * 4
        self._reserve_space(chunk_table_size)
        
        # Write chunks
        chunk_sizes = []
        for i in range(chunk_count):
            start = i * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, len(data))
            chunk_data = data[start:end]
            
            compressed_chunk = self._compress_sqsh_chunk(chunk_data)
            chunk_sizes.append(len(compressed_chunk))
            
            self._write_bytes(compressed_chunk)
        
        # Now write the chunk table (backfill)
        buffer_offset = chunk_table_offset - 0x14
        for i, size in enumerate(chunk_sizes):
            struct.pack_into("<I", self.buffer, buffer_offset + i * 4, size)
        
        return chunk_table_offset

    def _compress_sqsh_chunk(self, data: bytes) -> bytes:
        """Compress a chunk using SQSH format."""
        uncompressed_size = len(data)
        
        if self.compression_mode == 0:
            # No compression
            compressed_payload = data
        elif self.compression_mode == 1:
            # LZ77 compression
            compressed_payload = self._compress_lz77(data)
        elif self.compression_mode == 2:
            # zlib compression
            compressed_payload = zlib.compress(data, level=9)
        else:
            raise ValueError(f"Unsupported compression mode: {self.compression_mode}")
        
        compressed_size = len(compressed_payload)
        
        # Build SQSH header (19 bytes)
        header = bytearray(19)
        header[0:4] = b"SQSH"  # magic
        header[4] = 0  # unknown byte
        header[5] = self.compression_mode  # compression type
        header[6] = 0  # encryption flag (not used in practice)
        struct.pack_into("<I", header, 7, compressed_size)
        struct.pack_into("<I", header, 11, uncompressed_size)
        
        # Calculate checksum (simple sum of bytes)
        checksum = sum(compressed_payload) & 0xFFFFFFFF
        struct.pack_into("<I", header, 15, checksum)
        
        return bytes(header) + compressed_payload

    def _compress_lz77(self, data: bytes) -> bytes:
        """Compress data using LZ77 with 12-bit window (mode 1).
        
        This implements the same LZ77 variant used by Total Annihilation:
        - 4096-byte sliding window
        - Control byte with 8 bits (LSB first)
        - Bit 0: literal, Bit 1: back-reference
        - Back-reference: 16-bit value with upper 12 bits = offset, lower 4 bits = length-2
        """
        if not data:
            return b""
        
        output = bytearray()
        pos = 0
        window = bytearray(4096)  # 12-bit window
        window_pos = 1  # Start at position 1 like the decompressor
        
        while pos < len(data):
            control_byte = 0
            control_bits = []
            chunk_start = len(output)
            
            # Reserve space for control byte
            output.append(0)
            
            # Process up to 8 symbols
            for bit_idx in range(8):
                if pos >= len(data):
                    break
                
                # Try to find a match in the window
                best_match_offset = 0
                best_match_length = 0
                
                # Maximum match length is 17 (encoded as 15 in lower 4 bits, +2)
                max_match = min(17, len(data) - pos)
                
                # Search backwards through recently added data for best match
                # This is more efficient than searching the entire window
                for offset in range(1, min(window_pos, 4096)):
                    # Quick check: does first byte match?
                    if window[(window_pos - offset) & 0xFFF] != data[pos]:
                        continue
                    
                    # Find match length
                    match_len = 1
                    while match_len < max_match:
                        win_idx = (window_pos - offset + match_len) & 0xFFF
                        if window[win_idx] != data[pos + match_len]:
                            break
                        match_len += 1
                    
                    # Update best match if this is better
                    if match_len > best_match_length:
                        best_match_length = match_len
                        # Calculate offset from current position
                        best_match_offset = (window_pos - offset) & 0xFFF
                        if best_match_offset == 0:
                            best_match_offset = 4096
                
                # Decide: literal or back-reference (need at least 2 bytes to be worth it)
                if best_match_length >= 2:
                    # Use back-reference
                    control_bits.append(1)
                    
                    # Encode: upper 12 bits = offset, lower 4 bits = length - 2
                    encoded = (best_match_offset << 4) | ((best_match_length - 2) & 0x0F)
                    output.append(encoded & 0xFF)
                    output.append((encoded >> 8) & 0xFF)
                    
                    # Update window
                    for i in range(best_match_length):
                        if pos + i >= len(data):
                            break
                        byte = data[pos + i]
                        window[window_pos] = byte
                        window_pos = (window_pos + 1) & 0xFFF
                    
                    pos += best_match_length
                else:
                    # Use literal
                    control_bits.append(0)
                    byte = data[pos]
                    output.append(byte)
                    
                    # Update window
                    window[window_pos] = byte
                    window_pos = (window_pos + 1) & 0xFFF
                    pos += 1
            
            # Write control byte (LSB first)
            control_byte = 0
            for i, bit in enumerate(control_bits):
                if bit:
                    control_byte |= (1 << i)
            output[chunk_start] = control_byte
        
        return bytes(output)

    def _write_directory_tree(self, dir_entry: DirEntry) -> int:
        """Write directory structure and return its offset."""
        dir_offset = self.current_offset
        
        # Count total entries (subdirs + files)
        entry_count = len(dir_entry.subdirs) + len(dir_entry.files)
        
        # Write directory header
        self._write_u32(entry_count)  # entry count
        self._write_u32(0)  # data_offset (unused)
        
        # Reserve space for entry table (9 bytes per entry)
        entry_table_offset = self.current_offset
        self._reserve_space(entry_count * 9)
        
        # Write strings and build entry table
        entries_data = []
        
        # Process subdirectories first
        for subdir in dir_entry.subdirs:
            name_offset = self._write_cstring(subdir.name)
            # Recursively write subdirectory
            info_offset = self._write_directory_tree(subdir)
            flags = 0x01  # directory flag
            entries_data.append((name_offset, info_offset, flags))
        
        # Process files
        for file_entry in dir_entry.files:
            name_offset = self._write_cstring(file_entry.name)
            # Write file info structure (8 bytes: chunk_table_offset, size)
            info_offset = self.current_offset
            self._write_u32(file_entry.chunk_table_offset)
            self._write_u32(file_entry.uncompressed_size)
            flags = 0x02  # compressed flag
            entries_data.append((name_offset, info_offset, flags))
        
        # Backfill entry table
        buffer_offset = entry_table_offset - 0x14
        for i, (name_offset, info_offset, flags) in enumerate(entries_data):
            entry_offset = buffer_offset + i * 9
            struct.pack_into("<I", self.buffer, entry_offset, name_offset)
            struct.pack_into("<I", self.buffer, entry_offset + 4, info_offset)
            self.buffer[entry_offset + 8] = flags
        
        return dir_offset

    def _write_cstring(self, s: str) -> int:
        """Write null-terminated string and return its offset."""
        offset = self.current_offset
        encoded = s.encode("ascii", errors="replace") + b"\x00"
        self._write_bytes(encoded)
        return offset

    def _write_u32(self, value: int) -> None:
        """Write a 32-bit unsigned integer."""
        self._write_bytes(struct.pack("<I", value))

    def _write_bytes(self, data: bytes) -> None:
        """Append bytes to buffer and advance offset."""
        self.buffer.extend(data)
        self.current_offset += len(data)

    def _reserve_space(self, size: int) -> None:
        """Reserve space in buffer (filled with zeros)."""
        self.buffer.extend(bytes(size))
        self.current_offset += size


def sha256sum(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assemble(extracted_root: Path, output_hpi: Path, 
             compression_mode: int = 2, encryption_key: int = 0,
             reference_hpi: Optional[Path] = None) -> None:
    """Assemble HPI archive from extracted directory."""
    
    assembler = HPIAssembler(extracted_root, compression_mode, encryption_key)
    assembler.assemble(output_hpi)
    
    output_hash = sha256sum(output_hpi)
    print(f"SHA-256: {output_hash}")
    
    # If reference provided, validate against it
    if reference_hpi and reference_hpi.is_file():
        from hpi_parser import HPIParser
        
        print("\nValidating against reference HPI...")
        parser = HPIParser(reference_hpi)
        parser.parse()
        
        # Verify all files match
        missing = []
        mismatched = []
        
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
        
        if missing:
            print(f"Warning: {len(missing)} files missing from extracted directory")
        if mismatched:
            print(f"Warning: {len(mismatched)} files don't match reference")
        
        if not missing and not mismatched:
            print("✓ All files validated successfully against reference")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reassemble a Total Annihilation HPI archive from extracted files."
    )
    parser.add_argument("extracted", type=Path, help="Directory containing extracted files")
    parser.add_argument("output", type=Path, help="Path for rebuilt HPI archive")
    parser.add_argument(
        "--reference", type=Path, 
        help="Optional reference HPI archive for validation"
    )
    parser.add_argument(
        "--compression", type=int, choices=[0, 1, 2], default=2,
        help="Compression mode: 0=none, 1=LZ77, 2=zlib (default: 2)"
    )
    parser.add_argument(
        "--key", type=int, default=0,
        help="Encryption key (0-255, default: 0 for no encryption)"
    )

    args = parser.parse_args()

    if not args.extracted.is_dir():
        raise SystemExit(f"Extracted directory not found: {args.extracted}")

    assemble(args.extracted, args.output, args.compression, args.key, args.reference)


if __name__ == "__main__":
    main()
