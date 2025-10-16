# Function Catalog – Phase 1 Snapshot

This document captures the Phase 1 deliverables for function discovery and categorisation.  
Raw data (2608 functions discovered via `r2 aaa`) is exported to `data/function_catalog.csv` with columns `address,size,name`.  
Below is a curated view highlighting representative functions per subsystem together with the evidence gathered during analysis.

## Startup & Runtime Infrastructure

| Function (addr) | Role Summary | Evidence Highlights |
| --- | --- | --- |
| `entry0` (`0x004e6fa0`) | PE entry stub; orchestrates OS version checks, critical init calls, command-line ingestion, and tail-calls `main`. | Disassembly walkthrough in `DISASSEMBLY_PROGRESS.md`; calls `fcn.004f1830`, `fcn.004eb040`, `fcn.004f1460`. |
| `main` (`0x0049eda0`) | Sets up SEH frame and passes control (four args) to the core orchestrator. | `pdf` output shows standard SEH pattern with handler `0x4fdae0`. |
| `fcn.0049e830` (`0x0049e830`) | Core startup/game-loop routine managing single-instance semaphore, subsystem boot, registry writes, message pump, and orderly shutdown. | Detailed analysis added to `DISASSEMBLY_PROGRESS.md`. |
| `fcn.004f1830` (`0x004f1830`) | Creates the game-private heap and bootstraps allocator state. | Calls `HeapCreate`, stores handle at `0x52b524`, invokes `fcn.004f22a0`. |
| `fcn.004eb040` (`0x004eb040`) | Thread-local storage (TLS) initialiser capturing thread ID and bookkeeping pointers. | Uses `TlsAlloc`, `TlsSetValue`, `GetCurrentThreadId`. |
| `fcn.004f1460` (`0x004f1460`) | Environment and command-line normaliser supporting mixed ANSI/Unicode scenarios. | Walks environment blocks via `GetEnvironmentStrings[A/W]`, handles multi-byte parsing, allocates buffers with `fcn.004e8890`. |

## Windowing & Display Setup

| Function (addr) | Role Summary | Key APIs / Calls |
| --- | --- | --- |
| `fcn.004b52e0` (`0x004b52e0`) | Seeds display-related globals with default 640×480 viewport, clip rects, and identity projection values. | Direct writes to offsets within the global config structure. |
| `fcn.004b5980` (`0x004b5980`) | Creates the main window, realises palettes/DCs, and shows DirectX error dialogs on failure. | Calls `SystemParametersInfoA`, `CreateWindowExA`, `ShowWindow`, `MessageBoxA`, and tears down DC/GDI objects. |
| `fcn.004b5510` (`0x004b5510`) | Primary DirectDraw device creation and capability probing. | Xrefs to `DirectDrawCreate`; delegates resource cleanup to `fcn.004b4ff0`. |
| `fcn.0047bf70` (`0x0047bf70`) | Secondary DirectDraw initialisation path (likely for compatibility or alternate adapters). | Also invokes `DirectDrawCreate` import stub. |
| `fcn.004c54f0` (`0x004c54f0`) | High-level renderer bootstrap: iterates resource descriptors, initialises surfaces, queues scene graph setup. | Chains through `fcn.004b4f10`, `fcn.004c5c60`, `fcn.004c59d0`, indicates texture/list processing. |
| `fcn.004c2cc0` (`0x004c2cc0`) | Frame tick hub called each message-loop iteration. Appears to drive render/update cadence before handing off to gameplay logic. | Invoked post message pump from `fcn.0049e830` and before `fcn.004916a0`. |

## Input & UI Handling

| Function (addr) | Role Summary | Key APIs / Calls |
| --- | --- | --- |
| `fcn.004c1b80` (`0x004c1b80`) | Keyboard state sampler for hotkeys and modifier tracking. | Multiple calls to `GetAsyncKeyState`. |
| `fcn.004c1d50` (`0x004c1d50`) | Processes additional key chords (arrow keys, mouse buttons) for UI overlays. | Also leverages `GetAsyncKeyState`; shares tables with `fcn.004c1b80`. |
| `fcn.004b4f10` (`0x004b4f10`) | Window class/services registration; manages callback tables used throughout the UI. | Receives selector IDs (e.g., `0x11`) from `fcn.004c54f0` to register UI handlers. |
| `fcn.004b4ff0` (`0x004b4ff0`) | Centralised cleanup for UI-linked DirectDraw/GDI resources (cursor surfaces, window DCs). | Iterates multiple pointers in the window state block, invoking vtable slot `+8` destructors. |
| `fcn.0042f960` (`0x0042f960`) | General-purpose string/registry helper reused when registering shell verbs and reading config (also drives UI text loading). | Called from core loop and resource loaders (`CDLISTS`, `cdshell`). |

## Audio, Resources & Game Subsystems

| Function (addr) | Role Summary | Key APIs / Calls |
| --- | --- | --- |
| `fcn.004cef90` (`0x004cef90`) | DirectSound device creation wrapper. | Calls import stub `DirectSoundCreate`, sets up sound buffers. |
| `fcn.004cee50` (`0x004cee50`) | Audio mixer/control initialisation invoked during startup chain. | Consumes configuration from `fcn.004b5980` and sets registry-driven volumes. |
| `fcn.004916a0` (`0x004916a0`) | Resource/media loader for the `CDLISTS` package; coordinates CD content, mission data, and resource list resets. | Calls `fcn.0042f960`, `fcn.004aeda0`, `fcn.004aef80`, `fcn.0047eee0`, and other data-management helpers. |
| `fcn.004c61f0` (`0x004c61f0`) | Game state allocator invoked after `CDLISTS` load; zeroes runtime buffers. | Interacts with same global block as `fcn.004916a0`. |
| `fcn.004d85a0` (`0x004d85a0`) | Common disposer for dynamically allocated resource lists (AI/mission data). | Called multiple times after resource resets to free handles. |
| `fcn.004c2bd0` (`0x004c2bd0`) | Gameplay timing helper invoked early in `fcn.0049e830` to seed scheduler values. | Accepts frame timing configuration; interacts with `fcn.004c1a60`. |

## Using the Catalog

- For exhaustive enumeration, parse `data/function_catalog.csv`.  
- To isolate callers of a Windows or DirectX API, use `r2 -q -c 'aaa; axt @ <import stub>' TotalA.exe` (examples documented above).  
- The highlighted functions anchor the Phase 1 architectural map and will serve as entry points for deeper subsystem dives in Phases 2–4.
