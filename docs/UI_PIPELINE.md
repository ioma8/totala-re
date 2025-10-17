# UI Pipeline Notes

Technical map of the UI system uncovered in `TotalA.exe`. The focus is the path from the `.GUI` definition files inside the HPI archives to the in-memory widgets that the engine renders and interacts with.

---

## High-level Flow

```
GUI-driven screen (e.g. main menu)
    │
    ├─► FUN_004263b0                # Screen bootstrapper
    │       ├─ normalises base path under "guis/"
    │       ├─ FUN_004aa8f0         # loads & parses <NAME>.GUI
    │       └─ FUN_004a81e0(…,0xC0) # stages widget surfaces, resources, event handlers
    │
    └─ Runtime loop
            ├─ FUN_004a81e0(…,flags)   # per-frame update/draw
            ├─ FUN_004a05e0 / …        # widget-specific draw helpers
            └─ Input dispatch          # button, slider, list-box, text editing logic
```

- `.GUI` files sit beneath `guis/` inside the shipped HPI archives.
- The engine treats `.GUI` files as TDF-like INI scripts: sections + key/value pairs eventually parsed by the generic config reader at `FUN_004c2ea0`/`FUN_004c46c0`/`FUN_004c48c0`.
- Widget metadata is stored in a heap block that contains a 0x15B-byte record per gadget. The first byte (`record[0]`) holds the widget type (see below).

---

## Loading `.GUI` definitions

### `FUN_004aa8f0(int ctx, char *guiName, uint flags)`

Responsible for opening the GUI file (and optional merging) and populating the widget table.

- **Path construction** – copies the “guis” base path from `ctx + 0x9b6` (`.GUI` loaders initialise this with `"guis\\"`), appends the `guiName`, and normalises slashes via `FUN_004baff0`.
- **HPI open** – `FUN_004bbc40` resolves the file handle via the global resource manager. Returns 0 on failure.
- **Allocation** – when `flags & 0x200` is clear, `FUN_004d83b0(guiName, 0x10F57)` allocates a `GuiResource` blob. The base of each record is at `block + 0x3F`, and subsequent records are laid out contiguously (size 0x15B).
- **Parsing** – `FUN_004aeac0` walks the TDF sections, producing one record per `control`. Each record contains:
  - Type byte (`record[0]`).
  - String IDs, offsets, hotkeys, etc. stored at fixed offsets (`record+2`, `record+0x13`, `record+0x15`, …).
  - Type-specific fields filled by the switch in `FUN_004aeac0` (item height, max chars, slider geometry, filenames).
- **Merging** – when `flags & 0x200` is set the loader merges the new records into an already active GUI (used for overlay panels).
- **Auto-wiring** – after parsing the loader searches for canonical gadget IDs such as `"PANEL"`, stage buttons, or cancel buttons, and centres/offsets them if necessary. It also aligns sliders around their knob sprites and registers hotkeys.
- **State flags** – `ctx + 0x18` is updated to point at the head of the GUI list; `record[4]` stores instantiation flags (bit 7 = auto stage, bit 11 relayout). `ctx+0x60` caches the “last hot control”, reset to `-1`.

### Parsing helper – `FUN_004aeac0`

The parser harness around the generic config reader.

1. `FUN_004c2ea0` initialises the config context.
2. `FUN_004c2f60` loads the GUI script (TDF/INI text).
3. Loop: `FUN_004c3e10`/`FUN_004c3e20` iterate sections and `FUN_004ad350` copies common control fields into the record.
4. Type-specific keys are consumed:
   - **Type 0 (`BUTTON`)** – `FUN_004ad890` pulls label, state flags, callback IDs.
   - **Type 1 (`IMAGE`/`PANEL`)** – `FUN_004adc70` sets texture rectangles.
   - **Type 2 (`LISTBOX`)** – `itemheight` plus optional palette (`record[-8]`), `filename`.
   - **Type 3 (`TEXTINPUT`)** – `maxchars`, `filename` for the text box art.
   - **Type 4 (`SLIDER`)** – `range`, `thick`, `knobpos`, `knobsize`.
   - **Type 5 (`LABEL`/`STATIC TEXT`)** – text lines + optional font alias.
   - **Type 6** – toggles `hotornot` bit in the record.
   - **Types 7 & 8** – raw `filename` assets (animated frames, drop-down list art).
   - **Type 10** – `nuttin` flag (appears to be placeholder/no-op entries).
5. `record[-8..-1]` hold string buffers (labels, filenames). `FUN_004c48c0` copies string values from the config into those buffers and optionally resolves them via `FUN_004c5740` (symbol/name lookup).
6. `*(short*)(block + 0xb6)` stores the number of populated records minus one.

---

## Instantiating & Rendering

### `FUN_004a81e0(int ctx, uint flags)`

The master “stage/update GUI” routine. Used both to build up a fresh screen (`flags` contains 0xC1 in most boot callers) and to refresh/draw it every frame (smaller flag combos from the main loop).

Key behaviours (in load mode, `flags & 1`):

1. **Alignment** – resolves `-1`/`-2` sentinel values in the GUI header to centre surfaces in the current resolution. Uses `FUN_004b6700/710` to get viewport size.
2. **Resource reset** – optionally clears existing “save-under” surfaces and un-stages list boxes (`flags & 0x20` bypasses save-under creation).
3. **Per gadget initialisation** – iterates each record (`record size 0x15B`) and performs type-specific setup (below).
4. **Surface allocation** – `FUN_004c69f0` creates a target surface for the GUI background (`"GUI_SURFACE"`) and an optional save-under surface (`"SAVE_UNDER"`). `FUN_004c6b70` copies background art onto the render target, offsetting by the GUI anchoring.
5. **Optional painting** – if a parent surface is provided (`ctx + 0x24`) the GUI surface is blitted onto it, otherwise `FUN_004b0230` blits it to the main framebuffer.

When `flags` omits bit 1, `FUN_004a81e0` still walks the records, but it only executes the per-control update functions (drawing, input handling) without reinitialising resources. Bit usage in practice:

| Flag | Meaning |
| ---- | ------- |
| `0x0001` | Full instantiate/reset |
| `0x0002` | Tear down surfaces (`destroy` path) |
| `0x0004` | Skip paint (update logic only) |
| `0x0020` | Don’t capture save-under |
| `0x0040` | “Refresh” mode (used after input updates) |
| `0x0080` | Differentiate between initial staging and re-entry |
| `0x0100` | Centre GUI |
| `0x1000` | Centre with 0x80 offset |

### Widget types & staging

`FUN_004a81e0`’s main loop dispatches per-type work. Key excerpts:

- **Type 0 / 0x0A (panel/static)** – copies background bitmaps into the GUI surface. Optional `BackTile` fallback when the named gadget art fails to load.
- **Type 1 (buttons)** – `FUN_004a5f40` handles drawing and state transitions. Textures are resolved earlier via `stagebuttn*`, `BUTTONS0`, `CHECKBOX`, or fallback lists.
- **Type 2 (list box)** – `FUN_004a1b40` builds scrollers using the `LISTBOX` art and populates scrolled text entries. Shared slider fields (`record+0xda`) clamp the viewport height.
- **Type 3 (text input)** – `FUN_004a4d70` renders the textbox and updates `record+0x138` with the current string; handles caret blinking and history.
- **Type 4 (slider)** – `FUN_004a3ef0` manages knob positioning and range mapping. Creates helper controls for the rail and arrows (`record+0x152` indicates orientation).
- **Type 5 (label / multi-line text)** – `FUN_004a56b0` draws static text, handling newlines and multi-language replacements (`|` separated tokens).
- **Type 6 (hand toggles / stage buttons)** – `FUN_004a4980` draws and records mouse focus rectangles, updates hover state.
- **Type 7/8 (image placeholder)** – `record+0x2b` holds a pointer to a `GAF` animation loaded earlier; `FUN_004a05e0` blits the proper frame.
- **Type 0x0B (image list)** – loads a `GAF` (or GAF-like) bundle into `record+0xd6`.
- **Type 0x0F (cursor hotspot)** – resolves the pointer sprite and stores in `record+0xb8`.
- **Type 0x12/0x17 (timers)** – use `FUN_004b6340()` to seed countdowns plus `record+0xc6` for the absolute expiry time.

At the end of staging the active-control index is re-evaluated (`*(ctx+0x20)`), ensuring that focus doesn’t land on disabled gadgets. If the current focus control is non-clickable the loader picks the next viable candidate.

### Drawing & input

In steady-state frames (no full reinitialisation):

1. The GUI surface is combined with the screen using the current save-under buffer if present (restoring the background under the GUI).
2. Each control type’s handler draws itself and queries input:
   - Buttons watch mouse-down/up events (`FUN_004a5f40`).
   - Sliders respond to drags (`FUN_004a3ef0`).
   - Text inputs process keyboard input (`FUN_004a4d70`) and route to the Win32 IME if needed.
   - Hotspots and timers call `FUN_004a4980`/`FUN_004a4660` to manage state transitions.
3. `FUN_004b0230` composites the final GUI onto the target surface (`ctx+0x24`) or the main framebuffer.
4. Teardown with `flags & 2` reverses the process, restoring the saved background, freeing per-control resources (GAF handles, stage button textures), and releasing the GUI surface.

---

## Resource Resolution & HPI Interaction

| API | Purpose | Notes |
| --- | ------- | ----- |
| `FUN_004bbc40(path)` | Returns a handle for the resource entry (`HPI` file or filesystem). | Used for `.GUI` scripts and art; paths have backslashes normalised beforehand. |
| `FUN_004b8c60` / `FUN_004b8d40` | Load “GAF” animation banks and look up named entries. | Called for button art (`stagebuttn1`, `BUTTONS0`, `CHECKBOX`, etc.). |
| `FUN_004bbe50` | Converts palette names (e.g. `guis\\palettes\\gui.pal`) into in-memory palettes. | UI surfaces expect palette pointers; stored in each record. |
| `FUN_004b0230` | High-level blitter: draws the GUI onto the current render target. | For buttons and labels it works with the palette resolved above. |

If direct lookups under the “guis” namespace fail, the loader falls back to the global resource handle stored at `ctx + 4` (this points at the broader `gamedata` resource pack). The code also recognises special-case strings (`stagebuttn_d`, `BackTile`, etc.) and switches to fallback art when the primary resource is missing.

---

## Control Record Layout (partial)

Offsets from the start of each 0x15B-byte gadget record (inferred from the loader):

| Offset | Size | Meaning |
| ------ | ---- | ------- |
| `+0x00` | 1 | Control type (see table above). |
| `+0x01` | 1 | Group/Category ID (used for slider/linkage). |
| `+0x02` | 0x10 | Control name (`ControlName` in `.GUI`). |
| `+0x13` | 2 | X offset relative to GUI origin. |
| `+0x15` | 2 | Y offset relative to GUI origin. |
| `+0x17` | 2 | Width (pixels). |
| `+0x19` | 2 | Height (pixels). |
| `+0x1B` | 4 | Flags (bitfield: 0x1 auto label, 0x80 checkbox, 0x4000 stage override, etc.). |
| `+0x2B` | 4 | Pointer to art resource (GAF record, palette pointer, etc.). |
| `+0x2F` | 4 | Secondary pointer (frames array / list entries). |
| `+0xBC` | 4 | Primary `GuiSurface *` (allocated in staging). |
| `+0xC0` | 4 | Global art bank handle for this GUI. |
| `+0xC4` | 4 | Pointer to “background” GAF entry. |
| `+0xD6` | 4 | Additional surface/animation pointer (type 0x0B, 0x0A). |
| `+0x13A` | 4 | Pointer to text-input font art. |
| `+0x14E` | 4 | Pointer to slider image bank. |
| `+0x152` | 1 | Slider orientation index. |
| `+0x17?` | ... | Control-specific scratch (text buffers, slider values, timers). |

The full structure varies per widget and continues beyond the offsets listed above. The parser pre-clears 0x56 dwords per record to zero.

---

## Key Callers & Screens

| Function | Purpose | Primary `.GUI` |
| -------- | ------- | ------------- |
| `FUN_004263b0` | Main menu shell. | `MAINMENU.GUI`, palette `palettes\\guipal.pal`. |
| `FUN_004a7960` | Pop-up message boxes. | `MSGBOX.GUI`, `YESORNO.GUI`. |
| `FUN_0049fa50` | Generic UI shell entry (loads language, fonts). | Called after each GUI load to reset the `ctx + 0x519` structure, which references language strings. |
| `FUN_0049fb10` | Resets mouse focus and hot control state. | Typically invoked after each GUI load. |

In each case the sequence is the same: instantiate context (`FUN_004aa8f0`), stage UI (`FUN_004a81e0`), then hand over to the main loop where `FUN_004a81e0` is invoked with refresh flags to render and process input every frame.

---

## Practical Takeaways for Reimplementation

- `.GUI` files can be treated as structured data: a header block defining screen anchoring/alignment, followed by a list of gadget definitions. Each gadget is keyed by a name string and type code.
- The render-time structures are split across:
  - A GUI header (`ctx + 0x18` → list of `GuiScreen` nodes, each holding the record array pointer at `+4`).
  - An array of fixed-size records (0x15B bytes) per gadget storing geometry, resource pointers, and state.
- Loader functions heavily reuse the generic config parser; replicating the TDF parser should give a faithful dataset to feed a reimplementation.
- Rendering stubs depend on global subsystems:
  - `FUN_004c69f0`/`FUN_004c6b70` for surfaces.
  - `FUN_004b8c60`/`FUN_004b8d40` for GAF sprite banks.
  - `FUN_004b0230` for blitting and `FUN_004b6340` for clock ticks.
- Input is not handled by the widgets themselves; instead each gadget type’s handler translates current mouse/keyboard state (queried via `FUN_004c1ab0`, `FUN_004c1b00`, etc.) into state transitions on the record.
- The careful save-under logic (mirroring the original DirectDraw path) explains why many UI pop-ups restore the scene underneath—reimplementations should track whether a GUI needs save-under (`flags & 0x20` suppresses it).

This mapping now links the on-disc `.GUI` assets (and supporting art/palette files) with the runtime structures, making it possible to reconstruct the UI system or extract enough metadata for a modern renderer. Additional work (outside this note) would catalogue the per-type handler functions (`FUN_004a5f40`, `FUN_004a1b40`, etc.) to fully decode event wiring.

## Reimplementation Status (MVP)

- A minimal renderer (`pygame_gui_mvp.py`) parses `.GUI` files and draws basic widgets using Pygame.
- Implemented:
  - TDF parsing with multi-line `text=` aggregation and numeric conversion.
  - Window sizing from `GADGET0.COMMON.width/height`.
  - Basic label and button rendering with hover/press and disabled state.
  - Default focus and ASCII quickkey activation.
  - Centering sentinels for gadget positions (`xpos/ypos = -1/-2`).
- Pending for parity:
  - Palette + art loading (PCX/GAF) and per-type art resolution.
  - Listbox, slider, and text input behaviors.
  - Save-under logic and overlay/merge (`flags & 0x200`).
  - Full per-type initialisation stubs (`FUN_004a5f40`, `FUN_004a1b40`, `FUN_004a4d70`, etc.).
