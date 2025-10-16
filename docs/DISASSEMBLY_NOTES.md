# Disassembly Analysis Progress - TotalA.exe

## Task Goal
Disassemble and analyze `TotalA.exe` to determine its main inner logic and understand how the program works.

## Related Files
- **TotalA.exe** - PE32 executable (32-bit Windows GUI application for Intel 80386 architecture)

## Tools Used
- **radare2 (r2)** - Primary disassembly and binary analysis tool
- **objdump** - Available as backup disassembler
- **file** - To identify binary format
- **strings** - To extract readable strings from the binary

## What Has Been Done

1. **File Identification**
   - Confirmed TotalA.exe is a PE32 executable (32-bit Windows GUI application)
   - Architecture: Intel 80386

2. **Initial Analysis with radare2**
   - Listed all functions (391+ functions identified)
   - Located main entry point at `0x0049eda0`
   - Identified entry0 at `0x004e6fa0`

3. **Main Function Analysis**
   - Disassembled the main function (92 bytes)
   - Main function sets up exception handling and calls `fcn.0049e830` with 4 parameters
   - Standard Windows GUI application setup detected

4. **String Analysis**
   - Discovered the application is **"Total Annihilation"** - a classic RTS (Real-Time Strategy) game
   - Found DirectX-related warning messages about Microsoft DirectX compatibility

## What Should Be Done Next

1. **Global State Inventory**
   - Catalogue the `.data` / `.bss` globals touched by `fcn.0049e830` (e.g., `0x51f31c`, `0x51f320`, `0x511de8`) for `DATA_STRUCTURES.md`.

2. **Frame Scheduler Deep-Dive**
   - Reverse `fcn.004c2cc0`, `fcn.004c1a60`, and related timing helpers to understand update cadence ahead of `GAME_LOOP.md`.

3. **Resource Loader Analysis**
   - Trace `fcn.004916a0`, `fcn.0042f960`, `fcn.004aeda0`, and `fcn.004aef80` to document CDLISTS/HPI ingestion for `RESOURCE_FORMATS.md`.

4. **Subsystem Staging Docs**
   - Use findings to seed `GAME_LOOP.md`, `GRAPHICS_SYSTEM.md`, and `RESOURCE_FORMATS.md`.

## Current Understanding

The executable is the main game binary for "Total Annihilation". The entry point performs:
- Windows version detection
- Command line parsing (including handling quoted paths)
- Startup info retrieval
- Module handle acquisition
- Call to main function which then invokes the core game logic

The program follows a standard Windows GUI application pattern with exception handling and proper initialization sequence before entering the main game logic.

## Detailed Findings

### Function Map (Key Functions Identified)
- **entry0** @ `0x004e6fa0` (391 bytes) - Program entry point
- **main** @ `0x0049eda0` (92 bytes) - Main function
- **fcn.0049e830** @ `0x0049e830` (1365 bytes) - Core logic function called by main
- Total functions identified: 391+

### Entry Point (entry0) Analysis @ 0x004e6fa0

**Setup & Initialization:**
1. Standard prologue with exception handling setup
2. Calls `GetVersion()` to detect Windows version
3. Stores version info at multiple memory locations:
   - `0x529ed8` - Major version (lower byte)
   - `0x529edc` - Minor version
   - `0x529ed4` - Combined version
   - `0x529ed0` - Build number

**Initialization Checks:**
4. Calls `fcn.004f1830` - returns boolean, exits with code 0x1c if fails
5. Calls `fcn.004eb040` - returns boolean, exits with code 0x10 if fails
6. Calls `fcn.004f15c0` and `fcn.004f0c50` - initialization functions
7. Calls `GetCommandLineA()` - stores result at `0x52b650`
8. Calls `fcn.004f1460` - stores result at `0x529f3c`, validates non-null

**Command Line Parsing:**
9. Sophisticated command line parsing with quote handling:
   - Detects quoted paths (starts with `"`)
   - Handles multi-byte characters (calls `fcn.004f0e10` to check character types)
   - Skips leading whitespace (space char = 0x20)
   - Properly increments through command line arguments

**Startup Configuration:**
10. Calls `GetStartupInfoA()` to retrieve startup information
11. Checks startup flags (tests bit 0 of startup info)
12. Uses startup info to determine initial display mode (default 0xa = 10)

**Main Execution:**
13. Calls `GetModuleHandleA(NULL)` to get current module handle
14. Pushes parameters and calls **main** @ `0x0049eda0`
15. Calls `fcn.004e4600` with main's return value (exit handler)

### Main Function Analysis @ 0x0049eda0

**Structure:**
- Sets up structured exception handling (SEH)
- Exception handler at `0x4fdae0`
- Exception registration at `0x4e6718`
- Stores ESP in local variable for stack frame management

**Core Logic Call:**
- Pushes 4 parameters onto stack (from various local variables)
- Calls `fcn.0049e830` - **THIS IS THE CORE GAME LOGIC**
- Sets return marker to 0xffffffff before cleanup

**Cleanup:**
- Restores exception handler from fs:[0]
- Standard epilogue (pop edi, esi, ebx, restore esp/ebp)
- Returns with `ret 0x10` (16-byte parameter cleanup)

### Windows API Calls Identified

**KERNEL32.dll:**
- `GetVersion()` - OS version detection
- `GetCommandLineA()` - Command line retrieval
- `GetStartupInfoA()` - Startup configuration
- `GetModuleHandleA()` - Module handle retrieval

### Memory Layout Observations

**Global Variables (Data Section):**
- `0x52b650` - Command line string pointer
- `0x529ed8` - Windows major version
- `0x529edc` - Windows minor version  
- `0x529ed4` - Combined version number
- `0x529ed0` - Windows build number
- `0x529f3c` - Result from initialization function

### Application Characteristics

1. **Windows GUI Application** - Not a console app
2. **DirectX-based** - Warning messages about DirectX compatibility found
3. **Multi-byte Character Support** - Handles complex character parsing
4. **Robust Error Handling** - Multiple validation checks during initialization
5. **Version-aware** - Explicitly checks Windows version
6. **Exception Handling** - Uses structured exception handling (SEH)

### String Artifacts Found

- "Total Annihilation" - Game title
- DirectX compatibility warning message (198 bytes at `0x004fd050`):
  ```
  Warning! The currently installed version of Microsoft%sDirectX may not 
  function properly with Total Annihilation.%sPlease install the version 
  of DirectX included on the%sTotal Annihilation setup CD.
  ```

### Architecture Notes

- **Calling Convention**: Uses stdcall (caller cleans stack with ret 0x10)
- **Register Usage**: Standard x86 conventions (eax for returns, ecx/edx for temps)
- **Stack Frame**: EBP-based stack frames with exception handling
- **Optimization Level**: Appears to be optimized (minimal debug info, compact code)

### Core Logic Function `fcn.0049e830`

**Purpose Overview**
- Acts as the main orchestration routine after `main` sets up SEH.
- Enforces a single-instance policy via a named semaphore (`"Total Annihilation"`).
- Initializes multiple subsystems (window class, shell integration, resource managers).
- Drives the Win32 message loop and dispatches per-frame/game updates.
- Persists user configuration back into the registry before exit.

**Execution Flow (Condensed)**
1. Calls `fcn.004da1d0` and `fcn.004d8e50` to prime internal runtime state.
2. Uses byte flag at `0x51f31c` to gate one-time startup logic; when unset it flips the flag and calls `0x4e4ac0` (likely global config load) before proceeding.
3. Invokes `fcn.0041d920`, then attempts to `OpenSemaphoreA("Total Annihilation")`; if it succeeds, the function returns immediately with `eax = -1` (secondary instance guard).
4. On first instance, creates the semaphore, calls `fcn.004e6480` and `fcn.004e4860` (module/path discovery & window class registration), and then hands control to `fcn.0049ee30` for command-line/startup argument processing.
5. After successful startup, runs a long initialization chain:
   - `fcn.004b52e0`, `fcn.004b5980`, `fcn.004b62d0`, `fcn.004b62c0` – populate global configuration blocks and UI assets.
   - `fcn.0041d4c0` – performs DirectX capability checks (observed via follow-on registry writes and warning strings).
   - `fcn.004c54f0`, `fcn.004b4f10`, `fcn.004cee50`, `fcn.00428bb0`, `fcn.00491200` – initialize graphics, input, audio, and gameplay subsystems.
6. Updates `HKEY_LOCAL_MACHINE\SOFTWARE\Classes\AudioCD\shell\cdshell` using `RegOpenKeyExA`, `RegQueryValueExA`, `RegSetValueExA`, `RegFlushKey`, and `RegCloseKey`. This mirrors the retail behavior that installs the "Play Total Annihilation" autoplay handler when the CD is present.
7. Enters the primary message/game loop:
   - Pumps messages through `GetMessageA`, `TranslateMessage`, and `DispatchMessageA`.
   - When no messages are pending, falls through to call chains rooted at `fcn.004c2cc0` and `fcn.004916a0` (core game tick/update and renderer).
   - Additional callbacks (`call ebp`, `call edi`, `fcn.00499090`, `fcn.004cf0b0`) suggest hooks for timer-driven and DirectInput refresh steps.
8. On termination, re-writes registry values (mirroring step 6) and calls `fcn.0042f960`/`fcn.004b6110` to tear down shell integration and subsystem state before restoring callee-saved registers and returning.

**Key Windows API Usage**
- `OpenSemaphoreA`, `CreateSemaphoreA` – single-instance enforcement.
- `RegOpenKeyExA`, `RegQueryValueExA`, `RegSetValueExA`, `RegFlushKey`, `RegCloseKey` – CD autoplay configuration.
- `GetMessageA`, `TranslateMessage`, `DispatchMessageA` – standard Windows GUI loop.

**Notable Globals**
- `0x51f31c` – startup bit flag preventing duplicate initialization.
- `0x51f320` – shared buffer handed to multiple subsystem initializers and registry writers.
- `0x5119b8` – default `"Play Total Annihilation"` shell command string copied into registry.
- `0x50971c` – pointer to `"Total Annihilation"` (used as semaphore name and UI caption).
