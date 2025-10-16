# TotalA.exe Architecture Overview

## High-Level Architecture

### Program Type
- **Platform:** Windows 32-bit (PE32 executable)
- **Architecture:** Intel 80386 (x86)
- **Type:** GUI Application (not console)
- **Graphics API:** DirectX (likely DirectX 5 or 6, circa 1997)
- **Compiler:** Microsoft Visual C++ (inferred from calling conventions and SEH usage)

## Startup Sequence

```
Program Start (entry0 @ 0x004e6fa0)
    │
    ├─> Windows Version Detection (GetVersion)
    │   └─> Store version info in globals
    │
    ├─> Early Initialization
    │   ├─> fcn.004f1830 (critical init, exit 0x1c on fail)
    │   ├─> fcn.004eb040 (secondary init, exit 0x10 on fail)
    │   ├─> fcn.004f15c0 (additional init)
    │   └─> fcn.004f0c50 (additional init)
    │
    ├─> Command Line Processing
    │   ├─> GetCommandLineA()
    │   ├─> fcn.004f1460 (parse/validate command line)
    │   └─> Handle quoted paths and multi-byte chars
    │
    ├─> Startup Configuration
    │   ├─> GetStartupInfoA()
    │   └─> Determine initial display mode
    │
    ├─> Module Setup
    │   └─> GetModuleHandleA(NULL)
    │
    ├─> Main Function Call (main @ 0x0049eda0)
    │   ├─> Setup SEH (Structured Exception Handling)
    │   └─> Call Core Logic (fcn.0049e830)
    │       ├─> Enforce single-instance semaphore ("Total Annihilation")
    │       ├─> Initialise windowing, DirectDraw/DirectSound, registry hooks
    │       └─> Enter message/game loop (GetMessageA → Translate → Dispatch → per-frame update)
    │
    └─> Exit Handler (fcn.004e4600)
```

## Memory Layout

### Code Section
- Entry point: `0x004e6fa0`
- Main function: `0x0049eda0`
- Core logic: `0x0049e830`
- 391+ functions identified

### Data Section (Global Variables)
| Address    | Purpose                          |
|------------|----------------------------------|
| 0x52b650   | Command line string pointer      |
| 0x529ed8   | Windows major version            |
| 0x529edc   | Windows minor version            |
| 0x529ed4   | Combined version number          |
| 0x529ed0   | Windows build number             |
| 0x529f3c   | Init function result             |

### Exception Handlers
- Exception handler: `0x4fdae0`
- Exception registration: `0x4e6718`

## Component Identification (Preliminary)

### Identified Systems
1. **Initialization System**
   - Windows compatibility checking
   - Command line parsing
   - Resource initialization

2. **Exception Handling System**
   - Structured Exception Handling (SEH)
   - Error exit codes (0x1c, 0x10)

3. **Graphics System** (DirectX-based)
   - DirectX compatibility warnings found
   - Display mode configuration
   - Rendering pipeline (to be analyzed)

4. **Resource Management** (suspected)
   - .HPI file format (totala1.hpi present)
   - File I/O operations (to be identified)

### Systems Status After Phase 1
- [x] Game Loop entry points located (message pump in `fcn.0049e830`, per-frame callbacks via `fcn.004c2cc0` and `fcn.004916a0`).
- [x] Input hooks identified (`fcn.004c1b80` polling `GetAsyncKeyState`).
- [x] Audio init traced (`fcn.004cef90`, `fcn.004cee50`).
- [ ] Network/Multiplayer (not yet analysed).
- [ ] Core gameplay logic (unit/AI/combat still pending deep dive).
- [x] UI/windowing pipeline documented (`fcn.004b5980`, `fcn.004b5510`, `fcn.004b4ff0`).
- [ ] Save/Load system (future phase).

## Calling Conventions

### Standard Usage
- **stdcall convention** - Callee cleans stack
- Example: `ret 0x10` (clean 16 bytes = 4 parameters)
- Registers: EAX (return), ECX/EDX (scratch), EBX/ESI/EDI (preserved)

### Exception Handling
- Uses Windows SEH (Structured Exception Handling)
- FS segment register for exception chain (fs:[0])
- Exception frames on stack

## External Dependencies

### Windows & DirectX APIs (Phase 1)
- See `API_USAGE.md` for a complete import map.
- Highlights:
  - `KERNEL32`: heap creation, TLS, file I/O, locale conversion.
  - `USER32`: window lifecycle, message pump, hotkey polling.
  - `GDI32`: palette/DC management for fallback rendering surfaces.
  - `ADVAPI32`: registry access for shell integration (Audio CD autoplay).
  - `TDRAW.dll` (`DirectDrawCreate`) and `DSOUND.dll` (`DirectSoundCreate`) invoked during graphics/audio initialisation.
  - `WGMUS.dll` WinMM helpers and `smackw32.DLL` cinematic playback stubs imported for multimedia subsystems.

### Third-Party Data
- Smacker (`smackw32`) and `TPLAYX` imports indicate bundled FMV playback support.
- No Winsock or DirectPlay imports observed in the main binary (multiplayer path likely deferred).

## Main Loop Architecture

```
main @ 0x0049eda0
    └─> fcn.0049e830 (core orchestrator)
         ├─> Setup single-instance semaphore ("Total Annihilation")
         ├─> Initialise subsystems
         │    ├─> fcn.004b52e0        (default display metrics)
         │    ├─> fcn.004b5980        (window class + DirectDraw bootstrap)
         │    ├─> fcn.004b5510        (DirectDrawCreate wrapper)
         │    ├─> fcn.004cef90        (DirectSoundCreate wrapper)
         │    ├─> fcn.004c54f0        (renderer/resource graph init)
         │    └─> Registry writes via RegOpenKeyExA / RegSetValueExA
         ├─> Message loop
         │    ├─> GetMessageA / TranslateMessage / DispatchMessageA
         │    └─> Idle path → fcn.004c2cc0 (frame tick) → fcn.004916a0 (resource/game update)
         └─> Shutdown
              ├─> Persist registry settings
              ├─> Release DirectDraw/GDI surfaces (fcn.004b4ff0)
              └─> Call fcn.004b6110 for final teardown
```

## Upcoming Analysis Targets (Phase 2+)

1. **Frame Scheduler & Timing**
   - `fcn.004c2cc0`, `fcn.004c1a60`, and associated globals (`0x51f410`, `0x51f320`) – capture tick cadence and delta-time handling.
2. **Resource Containers**
   - `fcn.004916a0`, `fcn.0042f960`, `fcn.004aeda0`, `fcn.004aef80` – decode CDLISTS/HPI loading pipeline.
3. **Graphics Pipeline Deep Dive**
   - `fcn.004c54f0`, `fcn.004c59d0`, `fcn.004c5c60` – map texture/surface allocation and scene setup.
4. **Input Abstraction**
   - `fcn.004c1b80`, `fcn.004c1d50`, `fcn.004b4f10` – document control-state structures prior to reimplementation.
5. **Audio Mixer**
   - `fcn.004cef90`, `fcn.004cee50`, `fcn.004cedc0` – trace DirectSound + WinMM interplay for later porting.

## String Artifacts & Clues

### Identified Strings
- "Total Annihilation" - Game title
- DirectX compatibility warning (198 bytes @ 0x004fd050)
- Multiple string formatting placeholders (%s)

### String Analysis Value
Strings can reveal:
- UI text and menus
- Error messages
- File paths
- Configuration keys
- Debug messages
- Feature flags

## Code Characteristics

### Optimization Level
- Moderate optimization (not heavily inlined)
- Some hand-optimization visible
- Function boundaries clear
- Reasonably readable assembly

### Code Patterns
- Standard MSVC prologue/epilogue
- Stack frame management via EBP
- SEH setup patterns
- Standard Windows API usage

## Analysis Strategy Forward

### Breadth-First Approach
1. Map all major systems at high level
2. Identify component boundaries
3. Document key data structures
4. Then deep-dive into each system

### Key Questions to Answer (Phase 2+)
1. How are units represented in memory?
2. How does the rendering pipeline transform unit/terrain assets each frame?
3. What is the update frequency/timing and where is the scheduler defined?
4. How are resources (.HPI contents, CDLISTS) parsed into in-memory structures?
5. How does networking work (absence of obvious imports suggests custom implementation)?
6. What is the AI decision-making process?
7. How are save/load or replay systems implemented?

## Risk Assessment

### Low Risk Areas
- Standard Windows API usage (well documented)
- DirectX calls (documented APIs)
- File I/O patterns

### Medium Risk Areas
- Custom resource formats (.HPI)
- Network protocol (if proprietary)
- Optimized inner loops

### High Risk Areas
- Hand-optimized assembly sections
- Undocumented data structures
- Implicit state machines
- Pointer arithmetic patterns

## Documentation Philosophy

### For Each Function
- Address and size
- Purpose (high-level)
- Parameters (type and meaning)
- Return value
- Side effects
- Called by / Calls
- Pseudocode when complex

### For Each Data Structure
- Size and alignment
- Field offsets and types
- Purpose of each field
- Relationships to other structures
- Where allocated/freed

### For Each System
- Purpose and responsibilities
- Key functions
- Data structures used
- Interaction with other systems
- State management

## Next Document Updates

1. Populate `DATA_STRUCTURES.md` with confirmed globals (`0x51f31c`, `0x51f320`, `0x5119b8`, etc.).
2. Start `GAME_LOOP.md` leveraging the main-loop call chain documented above.
3. Extend `GRAPHICS_SYSTEM.md`/`RESOURCE_FORMATS.md` once DirectDraw surface layouts and CDLISTS parsing are decoded.
