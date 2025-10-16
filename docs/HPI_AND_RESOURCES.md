# HPI Archives & Resource Pipeline

## HPI File Format Summary

### Header Layout (20 bytes)
| Offset | Field | Description |
| ------ | ----- | ----------- |
| 0x00 | `magic` | Always `"HAPI"` (ASCII) |
| 0x04 | `version` | Observed `0x00010000` |
| 0x08 | `file_size` | Raw size field (not consumed by the loader) |
| 0x0C | `key` | First byte of the encryption key DWORD |
| 0x10 | `dir_offset` | Absolute file offset to the root directory block |

### Encryption
- Transform the key once: `transformed = (((key >> 6) | (key << 2)) & 0xFF) ^ 0xFF`.
- Decrypt the payload starting at file offset `0x14`:
  ```python
  pos = (i + 0x14) & 0xFF
  decrypted[i] = pos ^ transformed ^ (~encrypted[i] & 0xFF)
  ```
- All offsets in directory entries remain absolute. `hpi_parser.py` converts them to buffer indices with `file_offset - 0x14` prior to slicing.

### Directory Blocks
- Each block starts with `entry_count` and `data_offset` (unused by totala.exe, preserved for completeness).
- Every entry is 9 bytes:
  - `name_offset` → absolute offset of a null-terminated ASCII string
  - `data_offset` → absolute offset of file payload or nested directory block
  - `flags` → bit0 directory, bit1 compressed (SQSH)
- Recursion continues while bit0 is set, building full paths. Leaf entries record the chunk table pointer (first `u32` at `data_offset`) and the uncompressed length (second `u32`).

### Chunk Tables & Payloads
- Files with `flags & 0x02` use a chunk table located at `data_offset`. The table is an array of little-endian `u32` compressed sizes; chunk count is derived from the expected uncompressed size: `(size + 0xFFFF) // 0x10000`.
- After the table, chunk payloads are laid out back-to-back. Each payload starts with the 19-byte `"SQSH"` header describing mode, encrypt flag, compressed length, uncompressed length, and checksum.
- When `flags & 0x02` is clear the file is stored verbatim at `data_offset`.

## SQSH Compression Modes
| Mode | Description |
| ---- | ----------- |
| 0 | Stored (no compression) |
| 1 | Custom 12-bit LZ77 (0x1000 window, flag bits in rolling byte) |
| 2 | zlib/DEFLATE |

Chunk header layout (`"SQSH"`, mode byte, encrypt flag, compressed size, uncompressed size, checksum). Our Python tooling mirrors totala.exe’s decoder, yielding raw file buffers ready for modern use.

### SQSH Decompression Walkthrough (Mode 1)
The LZ77 variant in TotalA mirrors `fcn.004d35f0` and is implemented in `hpi_parser.py::_decompress_lz77`:
- Maintain a 0x1000-byte ring buffer (`dbuf`) seeded with zero; write pointer `w1` starts at 1.
- Consume a control byte (`w3`). Each bit (LSB first) indicates literal (`0`) or back-reference (`1`).
- **Literal path** – copy the next source byte to the output and `dbuf[w1]`, then advance `w1 = (w1 + 1) & 0xFFF`.
- **Back-reference** – read a 16-bit value `count`. Upper 12 bits give `dptr = count >> 4`; lower 4 bits encode the length `(count & 0x0F) + 2`. Bytes are copied from `dbuf[dptr]`, wrapping both pointers with `& 0xFFF`. A `dptr` of zero terminates the chunk.
- After eight decisions the next control byte is loaded. If the chunk encrypt flag is set (rare), bytes are preprocessed by subtracting `(i ^ i)` before decompression.

Mode 2 delegates to zlib (`inflate`). Mode 0 simply copies the payload. In each mode the Python implementation truncates the result to the uncompressed length advertised in the SQSH header to guard against malformed archives.

## TMH/TMHF Audio Wrapper
Many sound effects include a 64-byte header prefixed `"TMH"`/`"TMHF"`:
- Contains internal metadata and a sample-rate hint near offset `0x14` (typically ≈22 kHz).
- Payload is raw PCM (usually mono 16-bit LE, occasionally 8-bit).
- `tmhf_to_wav.py` strips the header and emits canonical RIFF/WAVE files.

## Resource Loading Flow (`fcn.004916a0`)
1. **Check cache** – early exit if asset tables are already populated.
2. **Load `CDLISTS` profile** – reads INI data into `0x51e828`.
3. **Reset tables** – frees existing lists and string pools within the `0x511de8` global state.
4. **Parse & register** – helper routines populate per-CD metadata, pointer arrays, and string tables.
5. **Final staging** – cleans stale references and prepares runtime structures for gameplay.

The loader cooperates with the HPI tooling above to surface every shipped asset. See `hpi_parser.py` for a reference implementation.

## Implementation Notes (`hpi_parser.py`)
1. Read the 20-byte header (`HPIHeader`) and compute the transformed key.
2. Decrypt the archive from offset `0x14` onward.
3. Walk the directory tree recursively, converting absolute offsets to buffer indices when slicing strings or child blocks.
4. For file entries capture:
   - `size` (second `u32` at `data_offset`)
   - `chunk_table_offset` (first `u32` at `data_offset`)
5. When extracting:
   - Derive chunk sizes from the table.
   - Read each SQSH payload, dispatching to the appropriate decompressor.
   - Concatenate output, truncating to the advertised uncompressed size.
6. TMH/TMHF-wrapped audio files are post-processed by stripping the 64-byte header and writing a RIFF/WAVE wrapper (`tmhf_to_wav.py`).

These steps exactly mirror the behaviour observed in `totala.exe`, providing bit-for-bit identical payloads for all shipped archives.
