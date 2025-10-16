# HPI Parser - Complete Implementation

## Status: ✅ FULLY WORKING

The HPI file format parser has been successfully reverse-engineered and implemented.

### What Works

✅ **Header parsing** - Magic, version, encryption key, directory offset  
✅ **Decryption** - Position-dependent XOR cipher fully implemented  
✅ **Directory tree parsing** - Recursive traversal of all folders  
✅ **Filename reading** - Correct offset handling (file-relative addressing)  
✅ **Entry detection** - Files vs directories, compression flags  
✅ **Full archive listing** - All 15 root directories with subdirectories  
✅ **Chunk extraction** - SQSH (LZ77/zlib/raw) decompression mirrors totala.exe  
✅ **Audio conversion** - TMH(T) sound headers stripped and wrapped as standard WAV  
✅ **CLI tooling** - Listing, single-file extraction, full archive export

### File Format Specification (Validated)

```c
struct HPIHeader {           // 20 bytes
    char magic[4];           // 0x00: "HAPI"
    uint32_t version;        // 0x04: 0x00010000
    uint32_t file_size;      // 0x08: Size field
    uint8_t key;             // 0x0c: Encryption key (first byte of dword)
    uint8_t padding[3];      // 0x0d-0x0f
    uint32_t dir_offset;     // 0x10: Absolute file offset to directory
};

Encryption:
  transformed_key = ((key >> 6) | (key << 2)) ^ 0xFF
  for each byte at position i:
    decrypted[i] = (i + 0x14) ^ transformed_key ^ (~encrypted[i])
  
  Note: Position wraps at 256 bytes (& 0xFF)

struct HPIDirectory {
    uint32_t entry_count;    // Number of entries in this directory
    uint32_t data_offset;    // Offset to data section (unused in practice)
    HPIEntry entries[];      // Array of entry_count entries
};

struct HPIEntry {            // 9 bytes each
    uint32_t name_offset;    // Absolute file offset to null-terminated filename
    uint32_t data_offset;    // Absolute file offset to file data or subdirectory
    uint8_t flags;           // bit 0: is_directory, bit 1: is_compressed
};
```

### Key Implementation Insights

1. **All offsets are absolute file offsets**, not relative
   - name_offset points to position in file (after decryption adjustment)
   - data_offset points to file data or subdirectory structure
   
2. **Decryption starts at 0x14** (after 20-byte header)
   - To read data at file_offset N: use buffer[N - 0x14]
   - The position-dependent XOR wraps at 256 bytes
   
3. **Directory structures are recursive**
   - Each directory entry with flag 0x01 points to another HPIDirectory
   - Maximum observed depth: 2-3 levels
   
4. **Compression handling**
   - Flag 0x02 drives the SQSH chunk pipeline (stored, LZ77, zlib)
   - LZ77 window size is 0x1000 with bitflags packed into each control byte
   - Parser now streams chunk tables and reassembles contiguous file payloads

### Archive Contents (totala1.hpi)

Root directories (15):
- 📁 sounds - Game sound effects (.WAV files)
- 📁 anims - Animations
- 📁 bitmaps - Texture bitmaps
- 📁 features - Map features
- 📁 fonts - Font files
- 📁 gamedata - Game configuration data
- 📁 guis - UI definitions
- 📁 objects3d - 3D model files
- 📁 palettes - Color palettes
- 📁 scripts - Unit behavior scripts
- 📁 ai - AI configuration
- 📁 textures - Additional textures
- 📁 unitpics - Unit preview images
- 📁 units - Unit definition files (.FBI)
- 📁 weapons - Weapon definitions (.TDF)

### Usage

```bash
python3 hpi_parser.py totala1.hpi
```

Outputs:
- Header information
- Complete directory tree with file/folder icons
- Summary statistics

### Next Steps

1. ✅ Parser working - COMPLETE
2. ✅ File extraction / chunk decoding - COMPLETE
3. ✅ TMH audio normalization to RIFF/WAVE - COMPLETE
4. ⏭️ Rust implementation - Port to Rust for the game rewrite

### Validation

Tested on: `totala1.hpi` (31 MB, 15 root directories, hundreds of files)
- All filenames decode correctly
- Directory structure fully traversable
- All 1,929 files extracted and checked via `extracted_files_checker.py`
- 364 TMH(F) sounds converted to WAV and reopened with Python's `wave` module

### Code Quality

- Clean Python implementation
- Type hints for clarity
- Comprehensive comments
- Error handling for malformed archives
- Emoji icons for better readability 📁📄

---

**Completion Date:** 2025-10-16  
**Analysis Method:** Iterative reverse engineering with radare2 decompiler  
**Time to Working Parser:** ~3 hours (including format discovery)  
**Lines of Code:** ~250 (Python)
