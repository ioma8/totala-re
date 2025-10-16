# Resource Loading Notes – CDLISTS Chain (Phase 2)

First target: the initial resource pass kicked off from `fcn.0049e830` → `fcn.004916a0`. The goal here is to document what data flows across the loader functions so later phases can reverse the underlying file formats.

## High-Level Flow

1. **Probe Existing Entries**  
   - `fcn.004916a0` looks at `GameStatePtr[0x10]` via `fcn.004ce450`.  
   - If entries already exist (`eax > 0`), the function copies them into `0x51e84c` and exits early (no reload required).

2. **Load `"CDLISTS"` Profile Data**  
   - Otherwise it calls `fcn.0042f960("Total Annihilation", dst=0x51e828, bytes=0xaa0)`.  
   - `fcn.0042f960` is a thin wrapper around `fcn.004b6a00`, effectively “read profile/INI value → copy into buffer”.
   - The `0x51e828` buffer (2720 bytes) now holds the textual CD resource list.

3. **Reset Previous Tables**  
   - `fcn.00428730` clears supporting state (string table hasn’t been decoded yet, but it zeroes the same region before rebuilding).  
   - `fcn.004aeda0(GameStatePtr+0x519, flag)` iterates the pointer array at `[base + index*4 + 8]`, frees each entry via `fcn.004d85a0`, zeroes the slots, and clears `base+0x14`.  
   - The routine is invoked twice: once with flag `1`, once with flag `0`, meaning it wipes two parallel tables (likely CD paths vs. file handles).
   - `fcn.004aef80(GameStatePtr+0x519)` frees the secondary pointer at `[base+4]` (helper structure allocated alongside the array).

4. **Parse & Register CDLISTS**  
   - A sequence of helper calls (`fcn.00431920`, `fcn.00431a20`, `fcn.0042f8c0`, `fcn.0042a3b0`, `fcn.0047eee0`, `fcn.0042a010`) consume the freshly loaded buffer.  
   - These functions operate on the central game-state block (`0x511de8`) and populate offsets including `0x148d7`, `0x29a0`, `0x33a13`, `0x37e1b`, `0x3816b`, etc. Each helper targets a distinct cache (string tables, pointer vectors, per-CD descriptors). Detailed layouts will follow once those consumers are decoded.

5. **Clean Stale Pointers**  
   - After parsing, `fcn.004916a0` frees two additional dynamic lists:  
     * Offset `0x37e1b` – probably the previously active “CD track list”.  
     * Offset `0x29a0` – another resource table (map preview cache?).  
   - Both use `fcn.004d85a0` before writing zero, signalling these slots hold heap-allocated arrays.

6. **Final Staging Calls**  
   - `fcn.0042bcc0`, `fcn.00452370(GameStatePtr+0x12ef)`, and `fcn.00434b90` perform the final pass (likely generating derived structures such as directory caches or playlists).  
   - At the end, `ESI` is popped and the loader returns, leaving the global game state primed with the new CD metadata.

## Data Artefacts to Track

| Location | Purpose (current hypothesis) |
| --- | --- |
| `0x51e828` | Temporary buffer for the `"CDLISTS"` INI string (2720 bytes). |
| `GameStatePtr + 0x519` | Array-of-pointers container; indices reference CD entries. |
| `GameStatePtr + 0x29a0` | Pointer cleared during rebuild; downstream code treats it as a dynamically allocated block. |
| `GameStatePtr + 0x37e1b` | Similar pointer cleared after reload; likely another CD-related cache. |
| `0x51e84c` | Scratch area that receives the regenerated string list when no reload is required. |
| `GameStatePtr + 0x148d7` | Buffer freed by `fcn.00431920` before parsing a fresh list. |
| `GameStatePtr + 0x33a13` | Pointer array whose elements are released by `fcn.0042f8c0`/`fcn.0047f060`; count stored at `+0x33a0f`. |
| `GameStatePtr + 0x3816b` | 0x232-byte records iterated in `fcn.00431a20`; stores per-CD metadata. |

## Open Questions

- Confirm the exact format of the `"CDLISTS"` text written into `0x51e828` (likely `Key=Path` pairs).  
- Map the structures produced by `fcn.00431920` / `fcn.00431a20` to concrete file formats (HPI archives vs. loose directories).  
- Identify where the cleaned pointers (`+0x29a0`, `+0x37e1b`) are reallocated so we can annotate the resulting layout.

The next resource-format investigations should log the contents of `0x51e828` at runtime and symbolise the helper routines above; the notes here give us the skeleton to do so.
