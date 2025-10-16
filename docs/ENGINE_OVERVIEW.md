# Engine Overview

## Platform Snapshot
- **Executable:** `TotalA.exe` (PE32 GUI application)
- **Platform:** Windows 95/NT era, DirectX 5/6 APIs
- **Compiler:** Microsoft Visual C++ (SEH + stdcall patterns)
- **Rendering & Audio:** DirectDraw for 2D surfaces, DirectSound for audio mixing, GDI fallback for UI overlays

## Startup Pipeline
1. **entry0** (`0x004e6fa0`) – detects OS version, sets up TLS and the main heap.
2. **Window/Class registration** – creates the primary game window, registers message handlers, and initialises DirectDraw/DirectSound (fallbacks use GDI).
3. **Resource bootstrap** – loads configuration and CD resource lists (`fcn.004916a0`) before dropping into the main loop.

## Main Message Loop (`fcn.0049e830`)
```c
while (GetMessageA(&msg, NULL, 0, 0) > 0) {
    TranslateMessage(&msg);
    DispatchMessageA(&msg);

    if ((g_flags[0x51f410] >> 11) & 1) {
        continue; // throttled
    }

    scheduler_drain();   // fcn.004c2cc0
    game_update();       // fcn.004916a0
}
```
- Standard Win32 pump; idle-time work handles game simulation and resource tasks.
- Throttle flag (bit 11 of `0x51f410`) skips frames when the engine requests (modal dialogs, heavy I/O).
- All per-frame logic hangs off the two calls above; additional systems (input, rendering, networking) enqueue work into the scheduler before each frame.

## Frame Timing & Scheduler
- **Base cadence:** 100 ms (≈10 FPS) via `GetTickCount()` stored at `0x51fb94`.
- **Scheduler block:** `0x51fbd0` – contains the 20-entry task queue, processing flags, and cleanup pointers.
- **Drain routine:** `fcn.004c2cc0` executes up to 20 queued tasks, sleeping 100 ms between iterations when work remains.
- **Interval clamp:** `fcn.004c1a60` caps frame interval at 30 ms to prevent runaway sleeps.

### Scheduler Control Block (0x51fbd0)
| Offset | Meaning |
| ------ | ------- |
| `+0x18a` | Pointer to the 20-entry task queue |
| `+0x1c2 .. +0x1c6` | Cleanup pointers freed prior to each drain |
| `+0x1ca` | “Active” flag (non-zero while draining) |
| `+0x1d6` | Processing flag toggled when a drain starts |

Tasks are enqueued by subsystems (resource streaming, animation scripts, networking). Before processing, `fcn.004c2cc0` frees the cleanup pointers, sets the active flag, executes up to 20 tasks (sleeping 100 ms between batches), then clears the flag.

### Per-frame Flow
1. **Message pump** – handles OS events and input translation.
2. **Throttle gate** – bit 11 of `0x51f410` skips the frame when the engine demands (cutscenes, blocking dialogs).
3. **Scheduler drain (`fcn.004c2cc0`)** – runs queued asynchronous work.
4. **Game update (`fcn.004916a0`)** – core simulation step:
   - Verifies CD/resource registrations; reloads `CDLISTS` when required.
   - Clears and rebuilds caches inside the `0x511de8` global state (string tables, resource pointers, map data).
   - Dispatches helper routines (`fcn.0042bcc0`, `fcn.00452370`, `fcn.00434b90`) that stage gameplay systems, animations, and audio state.
   - Sets up subsequent scheduler tasks (unit updates, rendering prep) for the next frame.
5. **Rendering and audio** – executed via DirectDraw/DirectSound using work queued during steps 3–4.

## Resource Loader Highlights
- `fcn.004916a0` manages CD/asset scanning:
  - Reads the `CDLISTS` profile into `0x51e828`.
  - Clears and repopulates resource caches located throughout the `0x511de8` global state.
  - Frees stale pointers before staging new structures via helper routines (`fcn.0042bcc0`, `fcn.00452370`, etc.).

## Global State Anchors
| Address | Role |
| ------- | ---- |
| `0x511de8` | Master game state structure (“god object”) |
| `0x51f320` | Window/display context |
| `0x51f410` | Global runtime flags |
| `0x51fbd0` | Frame scheduler control block |
| `0x51e828` | Scratch buffer for `CDLISTS` data |

For deeper disassembly notes, see `docs/DISASSEMBLY_NOTES.md` and `docs/DATA_STRUCTURES.md`.
