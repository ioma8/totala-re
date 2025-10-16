# Global Data Structures – Phase 2 Kickoff

This note captures the key globals touched during startup (`entry0 → main → fcn.0049e830`) so future work can reference concrete state locations. Addresses are absolute within TotalA.exe.

## Process/Environment Globals
| Address        | Size | Description | Observed In |
| ---            | ---  | --- | --- |
| `0x52b524`     | 4    | Handle returned by `HeapCreate`; acts as the game-private heap. Destroyed on init failure (`fcn.004f1830`). | `entry0`, `fcn.004f1830` |
| `0x52b650`     | 4    | Pointer to the raw command-line string from `GetCommandLineA`. | `entry0` |
| `0x529ed0`     | 4    | OS build number extracted from `GetVersion`. | `entry0` |
| `0x529ed4`     | 4    | Packed major/minor version result from `GetVersion`. | `entry0` |
| `0x529ed8`     | 4    | Windows major version (low byte). | `entry0` |
| `0x529edc`     | 4    | Windows minor version (low byte). | `entry0` |
| `0x529f3c`     | 4    | Pointer returned by `fcn.004f1460` after command-line normalisation. Used later when arguments are enumerated. | `entry0`, `fcn.0049e830` |

## App Startup Flags & Window Parameters (`gAppCtx`)

Address range `0x51f320`–`0x51f734` behaves as a global structure initialised before any subsystem spins up. It is passed by address to many routines (e.g. `fcn.004b52e0`, `fcn.004b5980`). Known fields so far:

| Offset | Address     | Meaning / Usage | Initial Value |
| ---    | ---         | --- | --- |
| `0x000` | `0x51f320` | First parameter forwarded from `main` (likely application instance / context pointer). | Loaded from `fcn.0049e830` arg3. |
| `0x004` | `0x51f324` | Stored copy of local pointer (`var_bch` in `fcn.0049e830`), used when setting up the window class (exact type TBD). | Set before registering `WNDCLASS`. |
| `0x008` | `0x51f328` | Pointer to the `"Total Annihilation"` window class name string (`0x509724`). | Populated during initial window-class construction. |
| `0x014` | `0x51f334` | Cleared to zero during boot; likely flag field reserved for runtime state. | `0`. |
| `0x1FA` | `0x51f51a` | Default render width (640). Written before DirectDraw init. | `0x280`. |
| `0x1FE` | `0x51f51e` | Default render height (480). | `0x1e0`. |
| `0x202` | `0x51f522` | `WNDCLASS.style` bitfield. Bits 0..7/8..15 receive `CS_*` flags (`0x02`, `0x10`, `0x20`, `0x40`, `0x80`, etc.). | Computed each launch. |
| `0x294` | `0x51f5b4` | Part of the window/resource state block touched by `fcn.004b5980` (exact semantics pending). | Zeroed at startup. |
| `0x614` | `0x51f934` | Set to `0x3f800000` (float 1.0), used by rendering math routines. | `1.0f`. |
| `0x620` | `0x51f940` | Receives `SystemParametersInfoA` data (window metrics). | Depends on host system. |
| `0x728` | `0x51fa48` | Cleared and later updated by UI initialisation; marks cursor/state readiness. | `0`. |

Additional contiguous fields within this block are manipulated heavily by `fcn.004b5980` (window creation), `fcn.004b4ff0` (resource cleanup), and `fcn.004c54f0` (renderer bootstrap). A detailed layout will follow once those routines are fully decoded.

### Startup Gate
- `0x51f31c` (`uint8 gStartupFlags`): bit `0` tracks whether the one-time system initialiser (`fcn.004e4ac0`) has run. Additional bits mirror the window-class style configuration (`al` mutations in `fcn.0049e830`) and deserve mapping as we refine the structure.

## Language / Locale Helpers
- `0x51fb48`: pointer used while reading `"language"` from the registry (`HKEY_LOCAL_MACHINE\SOFTWARE\Classes\...\language`). Currently observed as a scratch buffer base; exact structure remains TBD.
- `0x51fb90`: cached pointer to the main game-state block (`0x511de8`). Written during loop initialisation before calling the CD list loaders.
- `0x51fb94`: last tick value returned by `GetTickCount`; used by the main loop to throttle updates to ≥100 ms steps.

## Global Game State Root
- `0x511de8`: pervasive pointer dereferenced across gameplay, resource, and UI functions (thousands of XREFs). The structure behind it appears to house most runtime systems (mission data, CD list cache, AI state, etc.). Phase 2 tasks include carving this structure into named sub-blocks when analysing `fcn.004916a0` and related loaders.

### CD Resource Tables (Offsets from `0x511de8`)
| Offset | Purpose | Notes |
| --- | --- | --- |
| `0x148d7` | Pointer freed by `fcn.00431920` before reloading CDLISTS (likely string table or concatenated path buffer). | Reset to `NULL` via `fcn.004d85a0`. |
| `0x33a0f` | Count of entries in the CD asset pointer array. | Cleared by `fcn.0042f8c0`. |
| `0x33a13` | Start of an array (4-byte entries) consumed by `fcn.0042f8c0` and freed via `fcn.0047f060` during CDLISTS refresh. | Each element appears to be a pointer to a per-CD descriptor. |
| `0x3816b` | Base of a block of 0x232-byte records; iterated and freed by `fcn.00431a20`. | Represents amortised metadata per track/list entry. |

---

**Next actions:** continue annotating `gAppCtx` as more offsets are decoded, and begin carving the `0x511de8` tree once the resource-loader trace is complete. All findings here will be mirrored into `DATA_STRUCTURES.md` as deeper analysis progresses.***
