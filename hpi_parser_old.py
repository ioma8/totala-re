#!/usr/bin/env python3
"""
Total Annihilation HPI File Format Parser
Based on reverse engineering analysis of TotalA.exe

HPI Format:
- Magic: "HAPI" (4 bytes)
- Header with encryption key
- Directory tree with files/folders
- XOR encryption for directory data
"""

import struct
import sys
from pathlib import Path

class HPIParser:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.data = self.filepath.read_bytes()
        
    def parse_header(self):
        """Parse the HPI header"""
        if len(self.data) < 20:
            raise ValueError("File too small to be valid HPI")
        
        # Read magic
        magic = self.data[0:4].decode('ascii')
        if magic != 'HAPI':
            raise ValueError(f"Invalid magic: {magic} (expected HAPI)")
        
        print(f"[+] Magic: {magic}")
        
        # Read header fields
        # Based on decompiled code:
        # offset 0x00: magic (4 bytes)
        # offset 0x04: unknown (4 bytes)
        # offset 0x08: unknown (4 bytes)  
        # offset 0x0c: encryption key (1 byte)
        # offset 0x10: directory offset (4 bytes)
        
        version = struct.unpack('<I', self.data[4:8])[0]
        unk1 = struct.unpack('<I', self.data[8:12])[0]
        unk2 = struct.unpack('<I', self.data[12:16])[0]
        
        print(f"[+] Version/flags: 0x{version:08x}")
        print(f"[+] Unknown1: 0x{unk1:08x}")
        print(f"[+] Unknown2: 0x{unk2:08x}")
        
        # The directory offset is after decryption at position 0x10
        # But we need to decrypt first
        
        return {
            'magic': magic,
            'version': version,
            'unk1': unk1,
            'unk2': unk2
        }
    
    def decrypt_directory(self, key, offset, size):
        """
        Decrypt directory data using XOR cipher
        Based on fcn.004bdd70 decompiled code:
        
        key = ((key >> 6) | (key << 2)) ^ 0xFF
        for i in range(size):
            byte = data[i]
            pos = i + 0x14
            byte = ~byte & 0xFF
            data[i] = pos ^ key ^ byte
        """
        if key == 0:
            print("[+] No encryption (key=0)")
            return self.data[offset:offset+size]
        
        # Transform key
        transformed_key = (((key >> 6) | (key << 2)) & 0xFF) ^ 0xFF
        print(f"[+] Encryption key: 0x{key:02x} -> 0x{transformed_key:02x}")
        
        decrypted = bytearray()
        for i in range(size):
            byte = self.data[offset + i]
            pos = (i + 0x14) & 0xFF  # Position byte
            byte = (~byte) & 0xFF    # Invert
            result = pos ^ transformed_key ^ byte
            decrypted.append(result)
        
        return bytes(decrypted)
    
    def parse_directory(self, data, base_offset=0, indent=0):
        """
        Parse directory structure
        
        Directory format:
        - uint32: number of entries
        - uint32: offset to file data
        
        For each entry (9 bytes):
        - uint32: offset to filename string
        - uint32: offset to data/subdirectory  
        - uint8: flags (bit 0=is_dir, bit 1=compressed)
        """
        if len(data) < 8:
            return None
        
        prefix = "  " * indent
        
        num_entries, data_offset = struct.unpack('<II', data[0:8])
        if indent == 0:
            print(f"\n[+] Root Directory: {num_entries} entries, data offset: 0x{data_offset:08x}")
        
        entries = []
        for i in range(num_entries):
            entry_offset = 8 + (i * 9)
            if entry_offset + 9 > len(data):
                break
            
            name_offset, file_offset, flags = struct.unpack('<IIB', 
                data[entry_offset:entry_offset+9])
            
            # Read filename (null-terminated string)
            name = ""
            if name_offset < len(data):
                name_end = data.find(b'\x00', name_offset)
                if name_end > 0:
                    name = data[name_offset:name_end].decode('ascii', errors='ignore')
            
            is_dir = bool(flags & 0x01)
            is_compressed = bool(flags & 0x02)
            
            entry_type = "DIR " if is_dir else "FILE"
            comp_flag = "COMP" if is_compressed else "    "
            
            print(f"{prefix}[{entry_type}] [{comp_flag}] 0x{file_offset:08x} - {name}")
            
            # Recursively parse subdirectories
            if is_dir and file_offset < len(data) and indent < 5:  # Limit depth
                try:
                    self.parse_directory(data, file_offset, indent + 1)
                except Exception as e:
                    print(f"{prefix}  [!] Failed to parse subdirectory: {e}")
            
            entries.append({
                'name': name,
                'offset': file_offset,
                'is_dir': is_dir,
                'is_compressed': is_compressed,
                'flags': flags
            })
        
        return entries
    
    def analyze(self):
        """Main analysis function"""
        print("=" * 70)
        print(f"HPI File Analysis: {self.filepath.name}")
        print("=" * 70)
        
        header = self.parse_header()
        
        # Try to find encryption key and directory offset
        # The key is typically at offset 0x0c in the header structure
        # But after the 0x14 byte header, data is encrypted
        
        # Read potential encryption key from offset 0x0c
        encryption_key = self.data[0x0c]
        print(f"\n[+] Potential encryption key at 0x0c: 0x{encryption_key:02x}")
        
        # Try to decrypt starting from offset 0x14 (20 bytes)
        # First, we need to know the directory offset, which itself might be encrypted
        
        # Let's try decrypting a small section to see if we can find patterns
        sample_size = min(1024, len(self.data) - 0x14)
        decrypted_sample = self.decrypt_directory(encryption_key, 0x14, sample_size)
        
        print("\n[+] Decrypted sample (first 256 bytes):")
        print(decrypted_sample[:256].hex())
        
        # Try to parse as directory
        try:
            entries = self.parse_directory(decrypted_sample)
            if entries and len(entries) > 0 and len(entries) < 10000:
                print("\n[+] Successfully parsed directory structure!")
            else:
                print("\n[-] Directory parsing yielded suspicious results")
        except Exception as e:
            print(f"\n[-] Failed to parse directory: {e}")
        
        return header

def main():
    if len(sys.argv) < 2:
        print("Usage: python hpi_parser.py <hpi_file>")
        sys.exit(1)
    
    parser = HPIParser(sys.argv[1])
    parser.analyze()

if __name__ == '__main__':
    main()
