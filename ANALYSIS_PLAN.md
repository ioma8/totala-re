# Complete Binary Analysis Plan - TotalA.exe

## Ultimate Goal
Fully reverse engineer TotalA.exe (Total Annihilation) to understand its complete internal logic, data structures, and workflows for eventual rewrite in Rust.

## Analysis Methodology

### Phase 1: Architecture & Structure Mapping (**Completed**)
**Goal:** Understand the high-level program architecture and component organization

1. **Entry Point & Initialization Flow**
   - ✅ Map entry0 initialization sequence
   - ✅ Identify main function structure
   - ✅ Analyze core logic function (fcn.0049e830)
   - ✅ Document initialization dependencies and order (`ARCHITECTURE.md`)

2. **Function Discovery & Categorization**
   - ✅ Export function list with addresses and sizes (`data/function_catalog.csv`)
   - ✅ Categorize functions by purpose (`FUNCTION_CATALOG.md`)
   - ✅ Create function call graph for key components (`ARCHITECTURE.md`)

3. **API & Library Mapping**
   - ✅ List all Windows API calls (KERNEL32, USER32, GDI32, etc.) – see `API_USAGE.md`
   - ✅ Identify DirectX interfaces and calls
   - ✅ Map external dependencies
   - ✅ Document library initialization patterns (DirectDraw/DirectSound)

### Phase 2: Data Structure Analysis
**Goal:** Reverse engineer all major data structures used by the game

1. **Global State & Memory Layout**
   - Map .data section variables (global state)
   - Identify .bss section (uninitialized globals)
   - Document memory regions and their purposes
   - Find configuration variables

2. **Game Objects & Entities**
   - Identify unit/building structures
   - Map player state structures
   - Document projectile/weapon data
   - Reverse engineer terrain/map structures
   - Find AI state machines

3. **Resource Formats**
   - Analyze how .hpi files are loaded (totala1.hpi in directory)
   - Document texture/sprite formats
   - Understand sound file handling
   - Map configuration file parsing

### Phase 3: Core Systems Deep Dive
**Goal:** Fully understand each major subsystem

1. **Game Loop Architecture**
   - Identify main game loop location
   - Document frame timing and update logic
   - Map rendering pipeline
   - Understand input processing cycle
   - Find network tick handling

2. **Graphics & Rendering System**
   - DirectX initialization sequence
   - Rendering pipeline structure
   - 3D model rendering (units, terrain)
   - 2D UI rendering
   - Particle systems
   - Animation systems

3. **Game Logic Systems**
   - Unit AI and pathfinding
   - Combat mechanics and damage calculation
   - Resource collection and economy
   - Build queue management
   - Victory/defeat conditions

4. **Input & Control System**
   - Mouse input handling
   - Keyboard input processing
   - Command issuing logic
   - Camera control

5. **Network/Multiplayer System**
   - Network protocol identification
   - Synchronization mechanisms
   - Packet structures
   - Lobby/matchmaking

6. **Audio System**
   - Sound initialization
   - Music playback
   - 3D audio positioning
   - Sound effect triggering

7. **Resource Management**
   - File I/O patterns
   - Memory allocation strategies
   - .HPI archive handling
   - Texture/model loading

### Phase 4: Algorithm Analysis
**Goal:** Understand key algorithms and mathematical operations

1. **Pathfinding Implementation**
   - Algorithm type (A*, Dijkstra, etc.)
   - Grid/node representation
   - Optimization techniques

2. **Physics & Collision**
   - Projectile trajectories
   - Collision detection
   - Terrain interaction

3. **AI Decision Making**
   - Decision trees/state machines
   - Target selection
   - Formation handling

### Phase 5: Cross-Reference & Documentation
**Goal:** Create complete reference documentation

1. **Function Documentation**
   - Detailed pseudocode for each function
   - Parameter documentation
   - Return value meanings
   - Side effects noted

2. **Data Flow Diagrams**
   - How data moves through the system
   - State transitions
   - Event propagation

3. **Interaction Diagrams**
   - Component interactions
   - Sequence diagrams for key operations

## Documentation Structure

### Primary Documents
1. **ANALYSIS_PLAN.md** (this file) - Overall strategy and progress tracking
2. **DISASSEMBLY_PROGRESS.md** - Low-level disassembly findings
3. **ARCHITECTURE.md** - High-level architecture overview
4. **FUNCTION_CATALOG.md** - Complete function reference
5. **DATA_STRUCTURES.md** - All identified data structures
6. **GAME_LOOP.md** - Main game loop and timing
7. **GRAPHICS_SYSTEM.md** - Rendering pipeline documentation
8. **GAME_LOGIC.md** - Game mechanics and rules
9. **RESOURCE_FORMATS.md** - File formats and resource handling
10. **NETWORK_PROTOCOL.md** - Multiplayer networking details
11. **API_USAGE.md** - Windows/DirectX API usage patterns

### Supporting Documents (Created as needed)
- **MEMORY_MAP.md** - Complete memory layout
- **STRING_CATALOG.md** - All strings with context
- **CONSTANTS.md** - Magic numbers and their meanings
- **ALGORITHMS.md** - Key algorithm implementations
- **REVERSING_NOTES.md** - Techniques and insights during analysis

## Tools & Techniques

### Primary Tools
- **radare2** - Main disassembly and analysis tool
- **Ghidra** - Consider for decompilation if needed
- **IDA Free** - Alternative disassembler
- **x64dbg/OllyDbg** - Dynamic analysis and debugging

### Analysis Techniques
1. **Static Analysis**
   - Disassembly review
   - Control flow graph generation
   - Cross-reference analysis
   - String and constant analysis

2. **Dynamic Analysis** (if needed)
   - Debugging under Wine/Windows VM
   - Memory inspection
   - API call tracing
   - Breakpoint analysis

3. **Pattern Recognition**
   - Identify common compiler patterns (MSVC likely)
   - Recognize library code (C runtime, DirectX wrappers)
   - Find hand-optimized assembly sections

## Current Progress Tracking

### Phase 1: Architecture & Structure Mapping
- [x] Initial file identification
- [x] Entry point analysis (entry0)
- [x] Main function analysis
- [x] Core logic function (fcn.0049e830)
- [x] Function categorization (`FUNCTION_CATALOG.md`, `data/function_catalog.csv`)
- [x] API mapping (`API_USAGE.md`)
- [x] Call graph / subsystem overview (`ARCHITECTURE.md`)

### Phase 2: Data Structure Analysis
- [ ] Not started

### Phase 3: Core Systems Deep Dive
- [ ] Not started

### Phase 4: Algorithm Analysis
- [ ] Not started

### Phase 5: Cross-Reference & Documentation
- [ ] Not started

## Immediate Next Steps (Priority Order – Phase 2 Kickoff)

1. **Inventory Global Structures**
   - Dump `.data`/`.bss` symbols around `0x51xxxx` touched by the startup chain.
   - Begin documenting high-value globals in `DATA_STRUCTURES.md` (flags, config blocks, buffers).

2. **Map Resource Containers**
   - Trace callers of `fcn.0042f960`, `fcn.004916a0`, and related loaders to understand HPI/CD list layout.
   - Identify file formats and create scaffolding in `RESOURCE_FORMATS.md`.

3. **Isolate Frame Scheduler State**
   - Analyse `fcn.004c2cc0`, `fcn.004c1a60`, and timing globals to capture frame cadence ahead of `GAME_LOOP.md`.

4. **Plan Networking Recon**
   - Search the binary for Winsock/DirectPlay usage or custom netcode signatures to scope Phase 3 networking work.

## Success Criteria

Analysis will be considered complete when:
1. All major functions are documented with purpose and pseudocode
2. All data structures are reverse engineered with field names and types
3. Complete game loop is understood and documented
4. All subsystems have architectural documentation
5. Resource formats are fully documented
6. Network protocol is mapped (if applicable)
7. Sufficient detail exists to begin Rust reimplementation

## Estimated Timeline

- Phase 1: 2-3 weeks (detailed function-by-function analysis)
- Phase 2: 1-2 weeks (data structure reverse engineering)
- Phase 3: 3-4 weeks (system deep dives)
- Phase 4: 1-2 weeks (algorithm analysis)
- Phase 5: 1 week (documentation polish)

**Total Estimate:** 8-12 weeks of focused analysis

## Notes & Observations

- Binary appears to be MSVC compiled (Windows calling conventions, SEH)
- Optimization level appears moderate (not heavily obfuscated)
- Standard Windows GUI patterns make it more approachable
- Having the .hpi resource file is beneficial for understanding formats
- No obvious anti-debugging or obfuscation detected so far
- Game is from 1997, so DirectX 5/6 era APIs expected

---

## RAPID ANALYSIS UPDATE (2025-10-16)

**New Methodology:** Decompiler-first approach using radare2 pdc command

**Achievements (2-3 hours):**
- ✅ Main game loop completely understood (message pump, 100ms throttle)
- ✅ HPI file format fully reverse engineered (encryption + directory structure)
- ✅ Working Python parser created (hpi_parser.py)
- ✅ Resource loading pipeline traced (CDLISTS → HPI scanning)
- ✅ Frame scheduler decoded (task queue, timing)
- ✅ Key globals mapped (0x511de8 game state, 0x51fbd0 scheduler, etc.)
- ✅ SQSH compression behaviour replicated (LZ77 & zlib parity with totala.exe)
- ✅ TMH/TMHF audio wrapper documented; batch conversion pipeline to RIFF/WAVE

**New Documents:**
- RAPID_ANALYSIS.md - Comprehensive technical report
- PROGRESS_SUMMARY.md - Methodology and results
- hpi_parser.py - Working HPI file parser

**Speed Improvement:** 50-100x faster than manual assembly analysis

**Next Priorities:**
1. ✅ HPI parser complete - DONE (2025-10-16)
2. ✅ File extraction from HPI archives (chunk tables + SQSH decode)
3. ✅ Compression algorithm identification (LZ77 window 0x1000, zlib fallback)
4. Map 0x511de8 game state structure (5555 references)
5. Analyze graphics/audio initialization
6. Begin Rust reimplementation (HPI reader first) – can now mirror Python implementation

**Latest Update (2025-10-16 17:14 UTC):**
- HPI parser fully working after iterative debugging
- All offsets correctly interpreted (absolute file offsets)
- Complete directory tree parsing validated
- See HPI_PARSER_COMPLETE.md for full specification

See PROGRESS_SUMMARY.md for complete details.
