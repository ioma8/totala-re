#!/usr/bin/env python3
"""
Total Annihilation HPI File Format Parser - FIXED VERSION
Based on careful analysis of fcn.004bdd70 decompiled code

Key insights from reverse engineering:
1. Header is 20 bytes, followed by encrypted directory data
2. Encryption key at offset 0x0c transforms: key = ((key>>6)|(key<<2))^0xFF
3. Directory offset at header+0x10 needs pointer fixup (relative to header base)
4. All pointers in directory entries need fixup too
5. Directory format: [entry_count:4][data_offset:4][entries...]
6. Entry format (9 bytes): [name_offset:4][data_offset:4][flags:1]
"""

import struct
import sys
from pathlib import Path
from typing import Optional, Dict, List

class HPIHeader:
    def __init__(self, data: bytes):
        if len(data) < 20:
            raise ValueError("Header too small")
        
        self.magic = data[0:4]
        self.version = struct.unpack('<I', data[4:8])[0]
        self.file_size = struct.unpack('<I', data[8:12])[0]
        self.key = data[12]  # Encryption key is first byte of dword at offset 0x0c
        self.dir_offset_raw = struct.unpack('<I', data[16:20])[0]  # Offset 0x10
        
        # Transform the key as per decompiled code
        if self.key != 0:
            self.transformed_key = (((self.key >> 6) | (self.key << 2)) & 0xFF) ^ 0xFF
        else:
            self.transformed_key = 0
    
    def __repr__(self):
        return (f"HPIHeader(magic={self.magic}, version=0x{self.version:08x}, "
                f"size={self.file_size}, key=0x{self.key:02x}, dir_offset=0x{self.dir_offset_raw:08x})")

class HPIDirectory:
    def __init__(self, data: bytes, offset: int):
        if offset + 8 > len(data):
            raise ValueError(f"Directory at offset {offset} out of bounds")
        
        self.entry_count = struct.unpack('<I', data[offset:offset+4])[0]
        self.data_offset = struct.unpack('<I', data[offset+4:offset+8])[0]
        self.entries = []
        
    def __repr__(self):
        return f"HPIDirectory(entries={self.entry_count}, data_offset=0x{self.data_offset:08x})"

class HPIEntry:
    def __init__(self, name: str, name_offset: int, data_offset: int, flags: int):
        self.name = name
        self.name_offset = name_offset
        self.data_offset = data_offset
        self.flags = flags
        self.is_directory = bool(flags & 0x01)
        self.is_compressed = bool(flags & 0x02)
    
    def __repr__(self):
        type_str = "DIR" if self.is_directory else "FILE"
        comp_str = " COMPRESSED" if self.is_compressed else ""
        return f"{type_str:4s} {comp_str:11s} 0x{self.data_offset:08x} {self.name}"

class HPIParser:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.raw_data = self.filepath.read_bytes()
        self.header = None
        self.decrypted_data = None
        
    def decrypt_data(self, data: bytes, key: int, start_offset: int = 0x14) -> bytes:
        """
        Decrypt data using position-dependent XOR cipher
        Based on: data[i] = (i + start_offset) ^ key ^ (~data[i])
        
        Note: The position XOR uses only the low byte to wrap around
        """
        if key == 0:
            return data
        
        decrypted = bytearray()
        for i in range(len(data)):
            byte = data[i]
            # Position wraps at 256 for the XOR operation
            pos = (i + start_offset) & 0xFF
            byte = (~byte) & 0xFF
            result = pos ^ key ^ byte
            decrypted.append(result)
        
        return bytes(decrypted)
    
    def read_cstring(self, data: bytes, file_offset: int) -> str:
        """
        Read null-terminated string from data
        
        Args:
            data: Decrypted data buffer (starts at file offset 0x14)
            file_offset: Offset in the original FILE
            
        Returns:
            Null-terminated string
        """
        # Convert file offset to buffer offset
        # Data buffer starts at file offset 0x14
        buffer_offset = file_offset - 0x14
        
        if buffer_offset < 0 or buffer_offset >= len(data):
            return f"<invalid offset 0x{file_offset:x}>"
        
        end = data.find(b'\x00', buffer_offset)
        if end == -1:
            end = len(data)
        
        return data[buffer_offset:end].decode('ascii', errors='replace')
    
    def parse_directory(self, data: bytes, file_offset: int, depth: int = 0, path: str = "") -> List[HPIEntry]:
        """
        Recursively parse directory structure
        
        Args:
            data: Decrypted data buffer (starts at file offset 0x14)
            file_offset: Offset in the original FILE where this directory is
            depth: Current recursion depth (for display)
            path: Current path (for display)
        """
        # Convert file offset to buffer offset
        buffer_offset = file_offset - 0x14
        
        if buffer_offset < 0 or buffer_offset + 8 > len(data):
            print(f"{'  ' * depth}[!] Directory at file offset 0x{file_offset:x} out of bounds")
            return []
        
        # Read directory header
        entry_count = struct.unpack('<I', data[buffer_offset:buffer_offset+4])[0]
        data_section_offset = struct.unpack('<I', data[buffer_offset+4:buffer_offset+8])[0]
        
        # Sanity check
        if entry_count > 10000 or entry_count == 0:
            return []
        
        indent = "  " * depth
        if depth == 0:
            print(f"\n[+] Root Directory")
            print(f"    Entries: {entry_count}")
            print(f"    Data section offset: 0x{data_section_offset:08x}")
        
        entries = []
        total_files = 0
        total_dirs = 0
        total_compressed = 0
        
        # Parse each entry (9 bytes each)
        for i in range(entry_count):
            entry_buffer_offset = buffer_offset + 8 + (i * 9)
            
            if entry_buffer_offset + 9 > len(data):
                break
            
            name_file_offset = struct.unpack('<I', data[entry_buffer_offset:entry_buffer_offset+4])[0]
            data_file_offset = struct.unpack('<I', data[entry_buffer_offset+4:entry_buffer_offset+8])[0]
            flags = data[entry_buffer_offset+8]
            
            # Read filename (offset is in file coordinates)
            name = self.read_cstring(data, name_file_offset)
            
            # Create entry
            entry = HPIEntry(name, name_file_offset, data_file_offset, flags)
            entries.append(entry)
            
            # Count stats
            if entry.is_directory:
                total_dirs += 1
            else:
                total_files += 1
            if entry.is_compressed:
                total_compressed += 1
            
            # Display
            type_icon = "📁" if entry.is_directory else "📄"
            comp_str = " [COMP]" if entry.is_compressed else ""
            print(f"{indent}{type_icon} {entry.name}{comp_str}")
            
            # Recursively parse subdirectories
            if entry.is_directory and depth < 10:  # Limit recursion
                current_path = f"{path}/{name}" if path else name
                sub_entries = self.parse_directory(data, data_file_offset, depth + 1, current_path)
                entry.subdirectories = sub_entries
        
        # Show summary at depth 0
        if depth == 0:
            print(f"\n[+] Summary:")
            print(f"    Total directories: {total_dirs}")
            print(f"    Total files: {total_files}")
            print(f"    Compressed entries: {total_compressed}")
        
        return entries
    
    def parse(self):
        """Main parsing function"""
        print("=" * 70)
        print(f"HPI Archive Parser: {self.filepath.name}")
        print("=" * 70)
        
        # Parse header
        self.header = HPIHeader(self.raw_data[0:20])
        print(f"\n[+] Header Information:")
        print(f"    Magic: {self.header.magic.decode('ascii')}")
        print(f"    Version: 0x{self.header.version:08x}")
        print(f"    File size field: {self.header.file_size} bytes")
        print(f"    Directory offset (raw): 0x{self.header.dir_offset_raw:08x}")
        print(f"    Encryption key: 0x{self.header.key:02x} (transformed: 0x{self.header.transformed_key:02x})")
        
        if self.header.magic != b'HAPI':
            print(f"\n[!] ERROR: Invalid magic (expected 'HAPI', got '{self.header.magic}')")
            return None
        
        # Decrypt data starting from offset 0x14 (20 bytes)
        encrypted_section = self.raw_data[0x14:]
        self.decrypted_data = self.decrypt_data(encrypted_section, self.header.transformed_key)
        
        print(f"\n[+] Decrypted {len(self.decrypted_data)} bytes")
        print(f"    First 64 bytes (hex): {self.decrypted_data[:64].hex()}")
        
        # The directory offset in the header is an absolute file offset
        dir_file_offset = self.header.dir_offset_raw
        
        print(f"\n[+] Directory location:")
        print(f"    File offset: 0x{dir_file_offset:08x}")
        
        # Parse directory tree (pass file offset, it will be converted inside)
        try:
            entries = self.parse_directory(self.decrypted_data, dir_file_offset)
            print(f"\n[+] Successfully parsed {len(entries)} root entries")
            return entries
        except Exception as e:
            print(f"\n[!] Error parsing directory: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def extract_file(self, entry: HPIEntry, output_path: Path):
        """Extract a file from the archive (TODO)"""
        print(f"[!] File extraction not yet implemented")
        pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python hpi_parser.py <hpi_file>")
        print("\nThis parser will:")
        print("  - Decrypt the HPI archive")
        print("  - Display directory structure")
        print("  - Show all files and folders")
        sys.exit(1)
    
    parser = HPIParser(sys.argv[1])
    entries = parser.parse()
    
    if entries:
        print("\n" + "=" * 70)
        print(f"SUCCESS: Parsed HPI archive with {len(entries)} root entries")
        print("=" * 70)

if __name__ == '__main__':
    main()
