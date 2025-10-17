# Main Loop Analysis (`TotalA.exe::FUN_0049e830`)

This note distils the behaviour of the primary runtime loop recovered from `TotalA.exe` at address `0x0049e830`. The function is the first long-running routine entered from `main`, and it orchestrates subsystem bootstrap, the interactive message pump, and frame scheduling for the original Windows build of Total Annihilation.

## Entry & Bootstrap
- **Crash handler/semaphore** – `FUN_004da1d0(8)` installs the structured exception handler; `OpenSemaphoreA`/`CreateSemaphoreA` enforce a single-instance lock on `"Total Annihilation"`.
- **Command-line + environment** – `FUN_0049ee30` normalises arguments using the shared environment helpers described in `docs/ENGINE_OVERVIEW.md`.
- **Window context seed** – `FUN_004b52e0` zeros the global window/state blob anchored at `0x51f320`, stamping default 640×480 metrics (`0x280 × 0x1e0`) and storing the HINSTANCE/class strings in `0x51f32*`.
- **DirectDraw/DirectSound spin-up** – `FUN_004b5980` creates and shows the top-level window, realises palettes/DCs, and delegates device creation to `FUN_004b5510`. On success, the pointer at `DAT_00511de8 + 0x0c` is set to `&DAT_0051f320` so later subsystems can reach window state.
- **Subsystem warm-up** – `FUN_004b62d0`, `FUN_0041d4c0`, and `FUN_004b62c0` perform DirectX capability checks and cache probe results inside the master global block at `0x511de8`. Localisation is finalised by loading `language` from the registry (`FUN_0042f980`); blank values fall back to `"english"`.
- **Renderer/audio hooks** – `FUN_004c54f0` wires the renderer resource tables, `FUN_004b4f10` + `FUN_004cee50` produce the DirectSound control block saved at `DAT_00511de8 + 0x10`, and `FUN_00428bb0` / `FUN_00491200` initialise gameplay controllers and UI pipelines.
- **CD autoplay verb** – Before entering the loop the game writes an autoplay handler (`"cdshell"`) beneath `HKLM\SOFTWARE\Classes\AudioCD\shell`, storing the original value in `aBStack_68` so it can be restored later.

## Loop Overview

```text
while (true) {
    maybe_stage_audio();
    if (!have_messages && !needs_pump) {
        run_idle_tick();          // FUN_00499890
        tick_scheduler();         // ≥100 ms cadence via FUN_004cf0b0
        continue;
    }

    if (!GetMessageA(...)) {
        break;                    // WM_QUIT
    }
    TranslateMessage(); DispatchMessageA();
}

if (DAT_0051f410 bit 11) {
    FUN_004c2cc0();              // scheduler drain/cleanup
    FUN_004916a0();              // resource reload pass
}

restore_autoplay();
FUN_004b6110(&DAT_0051f320);     // teardown
return last_msg.wParam;
```

### Focus & Audio Staging
- **Active to idle** – When the activation flag `DAT_0051f400` clears and the DirectSound controller pointed to by `*(int **)(DAT_00511de8 + 0x10)` reports a non-null interface, the loop executes:
  - `FUN_00490f80()` – prepares audio state.
  - `FUN_004ce680()` – grabs a timestamp/capture handle, stored in `DAT_0051fb90`.
  - `FUN_004ce410()` – primes streaming buffers.
  - `DAT_00509720` is set to 1, marking that the audio front-end is staged.
- **Losing focus** – When `DAT_0051f400` becomes non-zero (minimise/Alt-Tab) and DirectSound reports inactive, the loop symmetrically unwinds:
  - `FUN_004ce260()` – pauses the device.
  - `FUN_004cd9d0()` binds a callback (`FUN_00490fe0`) for post-resume rebuild.
  - `FUN_004cedc0()` and `FUN_004ce7a0()` copy mixer flags from `DAT_00511de8 + 0x37f14/0x37f16`.
  - `FUN_004ce690()` restores the cached timestamp, then `FUN_00490fe0()` runs the global resume hook and `DAT_00509720` is reset to 0.

The pair of flags (`DAT_0051f400`, `DAT_00509720`) therefore track “window focused” and “audio staged” state respectively.

### Idle Tick Path (`FUN_00499890`)
Executed whenever the loop sees no pending Windows messages **and** gameplay isn’t suppressed (`DAT_0051f400 == 0` and bit 0 of `*(DAT_00511de8 + 0x2a44)` clears). Highlights:
- **Input polling** – `FUN_004c1b00()`/`FUN_004c1ab0()` fetch raw keyboard data, with hotkey handling for screenshot capture (scan code `0xd6`) and UI dismissals (codes `0x7e`, `0xe3`). Screenshot requests build the save path under `...\screenshots\` (`FUN_004e42b0`, `FUN_004cb170`).
- **Mouse state** – `FUN_004c2de0()` captures cursor deltas into two 6-word buffers. Depending on the window message codes captured (WM_MOUSEMOVE `0x200` vs button events `0x202/0x205`) the buffers are copied into the structure at `DAT_00511de8 + 0x2c76`, otherwise `FUN_004c2d60()` resets it.
- **UI/runtime driver** – `FUN_004b6370()` flushes deferred UI work. If the window flags at `*(DAT_00511de8 + 0x0c) + 0xf1` do not have bit 3 (`0x08`) set, the function pointer stored at `DAT_00511de8 + 0x391f5` executes — this is effectively the high-level “frame” callback registered during UI initialisation.

### Scheduler Maintenance
- Every idle iteration compares `GetTickCount()` against `DAT_0051fb94`. When the delta exceeds 99 ms, `FUN_004cf0b0(*(void **)(DAT_00511de8 + 0x10))` runs:
  - The routine enumerates up to eight entries in the table at `audioHandle+0x1c4` and 32 entries starting at `+0x38`, calling each vtable slot at offset `0x24`.
  - Items that report completion (return non-zero or null context) are removed and the owning list counts are decremented. If the overflow flag at `+0x1e4` is set, `FUN_004cfbc0` processes deferred releases.
- `DAT_0051fb94` is then refreshed to the current tick.

### Message Pump & Exit
- Standard Win32 loop: `PeekMessageA` only guards the idle work, while `GetMessageA` drives pump + dispatch. `WM_QUIT` (return 0) breaks the outer loop.
- If bit 11 of the runtime flag word at `DAT_0051f410` is set on exit, one final “drain” occurs:
  - `FUN_004c2cc0()` pulls the scheduler queue from the block returned by `FUN_004b6220()` (global at `0x51fbd0` per `docs/ENGINE_OVERVIEW.md`). It conditionally spins up to 20 × 100 ms sleeping batches (`FUN_004b6b50`) while waiting for the async flag at `+0x1d6` to clear, then frees cleanup lists at offsets `+0x1c{2,6}` and the task array at `+0x18a`.
  - `FUN_004916a0()` performs the per-frame resource refresh described below.
- Finally the CD autoplay registry entry is restored using the buffer captured at startup, and `FUN_004b6110(&DAT_0051f320)` tears down window/DC/DirectDraw state, matching the allocations performed by `FUN_004b5980`. The function returns the last message’s `wParam`.

## Resource Refresh Pass (`FUN_004916a0`)

`FUN_004916a0` is the “gameplay step” executed after the scheduler drain:
- Copies the current channel enable flags from the DirectSound control block into the byte array starting at `DAT_0051e84c`.
- Reloads `CDLISTS` into the scratch buffer at `DAT_0051e828`, then cascades the data through mission/asset caches (`FUN_00428730`, `FUN_004aeda0`, `FUN_004aef80`).
- Frees and rebuilds numerous pointer arrays inside the master state (`FUN_00431920`, `FUN_00431a20`, `FUN_0042f8c0`, `FUN_0042a3b0`, `FUN_0047eee0`, `FUN_0042a010`).
- Resets campaign/unit metadata stored at `DAT_00511de8 + 0x37e1b` and `+0x29a0`, then calls:
  - `FUN_004c61f0(0)` / `FUN_004c62c0()` – clear and repopulate scheduler-linked queues.
  - `FUN_0043c350()` – rebuilds map/object registries.
  - `FUN_0042bcc0()`, `FUN_00452370(DAT_00511de8 + 0x12ef)`, `FUN_00434b90()` – refresh script lists, gameplay tasks, and animation/audio glue that will feed into the next frame.

## Signals & Data Flow

| Global | Purpose | Producer(s) | Consumer(s) |
| ------ | ------- | ----------- | ----------- |
| `DAT_00511de8` | Master state root (window ctx, audio handle, scheduler data). | Initialised in bootstrap; mutated heavily in idle/resource passes. | Every per-frame helper (`FUN_00499890`, `FUN_004916a0`, scheduler). |
| `DAT_0051f400` | Window activation/focus flag. | Window procedure (outside current scope). | Focus/audio guard in main loop; idle gating. |
| `DAT_00509720` | Tracks whether audio buffers are staged. | Main loop focus handlers. | Prevents duplicate resume/pause calls. |
| `DAT_0051fb94` | Millisecond timestamp for scheduler maintenance. | Updated when `FUN_004cf0b0` runs. | Idle branch comparator. |
| `DAT_0051f410` bit 11 | “Drain once more” flag. | Set by subsystems requesting a final drain (e.g., modal interactions). | If set at exit, forces `FUN_004c2cc0()` + `FUN_004916a0()` before teardown. |
| `DAT_0051fb50` | Localised language string. | Registry load/fallback in bootstrap. | `FUN_004c54f0` (renderer localisation). |

## Takeaways
- The engine does not run a tight fixed-step loop; it leans on the Windows message pump and only performs heavy work during idle gaps. Scheduler maintenance is throttled to ~10 Hz via the `GetTickCount()` delta.
- Gameplay/resource refresh (`FUN_004916a0`) is decoupled from the idle tick and only invoked when `DAT_0051f410` requests it — typically after CD content changes or when modal UIs hand control back to the simulation.
- Audio focus handling is carefully staged to avoid DirectSound state corruption across focus changes, with explicit bookkeeping inside `DAT_00509720`.
- The registry lifting/restore of `"cdshell"` occurs both before entering and after leaving the loop to mirror the retail behaviour that advertises “Play Total Annihilation” for Audio CDs.

These observations should guide the clean-room reimplementation: the scheduler can remain message-driven with idle polling, the audio subsystem needs focus-aware staging, and resource refreshes should be triggered explicitly rather than every frame.
