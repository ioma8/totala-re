# Game Loop Notes (Phase 2)

Source functions:
- `fcn.0049e830` – main orchestrator called from `main`.
- `fcn.004c1a60` – clamps frame interval & zeroes scheduler counters.
- `fcn.004c2cc0` – processes the per-frame scheduler queue.
- `fcn.004b6b50` – wrapper around `Sleep`.
- Scheduler globals live at `0x51fbd0` (returned by `fcn.004b6220`).

## Message Pump Structure (fcn.0049e830)

1. **Get/Dispatch Messages**
   - `GetMessageA` fills a `MSG` on the stack (var_40h).  
   - Positive result: `TranslateMessage` → `DispatchMessageA`.  
   - The loop continues until `WM_QUIT` (negative result breaks and exits through `fcn.004b6110`, after clean-up).

2. **Idle Path (no message pending)**
   - Verifies `dword[0x51f410]` bit‑flags together with the scheduler block to ensure we are allowed to run a frame (skips if throttled).
   - `fcn.004c2cc0()` drains the scheduler queue.
   - `fcn.00499890` prepares sub-systems (input/audio prep).
   - `edi` is initialised once to `GetTickCount` (`mov edi, [sym.imp.KERNEL32.dll_GetTickCount]`). On every idle iteration we call it, compare against the last value stored at `0x51fb94`, and only advance the frame if the delta is ≥ `0x64` (100 ms). When the threshold is met, the new tick count is written back to `0x51fb94`.
   - After the throttle check, `fcn.004cf0b0` and follow-up helpers process subsystems (resource refresh, AI hooks, etc.) before looping back to `GetMessageA`.

## Scheduler Block (`0x51fbd0`)

`fcn.004b6220` returns the base pointer to this structure. Notable offsets observed so far:

| Offset | Meaning | Writers |
| --- | --- | --- |
| `+0x0f0` (byte) | Flag bits – bit1 gates `fcn.004c2cc0` (checked via `shr eax, 0xa` in the idle loop). | `fcn.004b5980`, `fcn.004c2cc0`. |
| `+0x0f2` (dword) | Frame interval in milliseconds. Set to `min(requested, 30)` by `fcn.004c1a60`. | `fcn.004c1a60`. |
| `+0x16e`, `+0x172` (dword) | Frame timers/counters zeroed by `fcn.004c1a60` on initialisation. | `fcn.004c1a60`. |
| `+0x18a` (dword) | Pointer to an allocation used for scheduling (array of 0x14 entries). Freed inside `fcn.004c2cc0`. | `fcn.004c2cc0`. |
| `+0x18e`, `+0x192` (dword) | Counters updated while draining the queue (modulo arithmetic). | `fcn.004c2cc0`. |
| `+0x1be`/`+0x1c2`/`+0x1c6` (dword) | Ancillary pointers that get passed to `fcn.004c6ac0` when resetting. | `fcn.004c2cc0`. |
| `+0x1ca` (dword) | Non-zero while a queue is being processed; cleared once idle work finishes. | `fcn.004c2cc0`. |
| `+0x1d6` (dword) | Boolean flag set to 1 when the pump starts draining, reset as slots empty out. | `fcn.004c2cc0`. |

### Related Globals
- `0x51fb90` – cached pointer to the main game-state block (`0x511de8`). Stored during loop initialisation and reused when calling helpers each frame.
- `0x51fb94` – last tick value returned by `GetTickCount` (used for the 100 ms throttle described above).

### `fcn.004c1a60` (Frame Interval Clamp)
1. Retrieves the scheduler (`fcn.004b6220`).  
2. If the requested interval (`arg_4h`) is greater than 30ms, writes 30; otherwise writes the requested value into `scheduler+0xF2`.  
3. Resets counters at `+0x16e` and `+0x172` to zero.

### `fcn.004c2cc0` (Idle Scheduler Drain)
1. Pulls the scheduler base. If `dword[scheduler+0x18a] == 0`, it simply returns.
2. Checks the high bit in `word[scheduler+0xF0]` to avoid re-entry while another drain is in progress.
3. If `dword[scheduler+0x1ca]` is non-zero, the queue is already active and it skips cleanup.
4. Otherwise it:
   - Pushes the three bookkeeping pointers (`+0x1c6/+0x1c2/+0x1be`) into `fcn.004c6ac0` (tear-down helper).
   - Frees the queue allocation via `fcn.004d85a0` and zeroes `+0x18a`.
   - Sets `dword[scheduler+0x1d6] = 1` and walks up to 20 slots, calling `fcn.004b6b50(0x64)` (Sleep 100ms) when necessary.
5. During the walk it copies 0x18-byte records from the queue, rotating counters at `+0x18e`, `+0x186`, etc., and stops once the head meets the tail.
6. When all work is done, it clears `dword[scheduler+0x1ca]`.

In short: `fcn.004c2cc0` drains any pending scheduled tasks each time the main loop goes idle, ensuring the queue doesn’t grow unbounded and inserting a short sleep to throttle processing if 20 iterations haven’t completed.

## Open Questions

- The function pointer at `0x51fb94` (invoked via `call edi`) needs identification; it is almost certainly the “real” per-frame update.
- Many helper calls within the idle branch (`fcn.00499890`, `fcn.004cf0b0`, `fcn.004c6ac0`) remain to be named – they likely cover audio, input, and timer management.
- Additional scheduler state (offsets `+0x180` onwards) should be documented once `fcn.004c6ac0` is decoded.

This overview should make Phase 2’s deeper dive into the scheduler manageable: map `0x51fbd0` completely, name the update function at `0x51fb94`, and trace how the queue entries are produced.***
