# TotalA Reverse Engineering (totala-re)

Rapid reverse engineering of Total Annihilation’s engine with emphasis on HPI resource archives and runtime subsystems.

## Goals
- Document the original Windows engine architecture and data flow well enough to guide a clean-room reimplementation (targeting Rust).
- Provide reliable tooling for unpacking game assets, validating extracted data, and converting proprietary formats (SQSH, TMH/F) into modern equivalents.
- Share progressive findings in a structured way so additional contributors can extend the work (AI, networking, rendering, etc.).

## Current Artefacts
- **Docs** – see `docs/PROJECT_PLAN.md`, `docs/ENGINE_OVERVIEW.md`, `docs/HPI_AND_RESOURCES.md`, plus supporting references in `docs/`.
- **Tools** – `hpi_parser.py`, `extracted_files_checker.py`, `tmhf_to_wav.py`, `hpi_assembler.py` support archive extraction, validation, audio conversion, and archive reassembly.
- **Status** – HPI/SQSH formats decoded, TMH audio normalised, groundwork laid for engine reimplementation.

## Tool Usage
```bash
# List archive contents (console view)
python3 hpi_parser.py totala1.hpi --list

# Extract everything into ./extracted
python3 hpi_parser.py totala1.hpi --extract-all extracted

# Sanity-check extracted assets
python3 extracted_files_checker.py extracted

# Convert TMH/TMHF audio to WAV
python3 tmhf_to_wav.py extracted/sounds converted_wav

# Rebuild archive, ensuring bit-identical output
python3 hpi_assembler.py totala1.hpi extracted totala1_rebuild.hpi

# Double-check hashes (optional)
shasum -a 256 totala1.hpi totala1_rebuild.hpi
```

Temporary outputs (e.g. `extracted/`, `converted_wav/`, `totala1_rebuild.hpi`) can be removed after verification.

## GUI MVP Renderer

A minimal Pygame-based renderer for `.GUI` files is available to validate parsing and layout against real assets.

Features (MVP):
- Parses TDF-style `.GUI` (sections like `[GADGETx]` and `[COMMON]`).
- Uses `GADGET0` width/height for window size.
- Renders labels and button-like controls with hover/press.
- Supports disabled/grayed state, default focus, and quickkeys (ASCII codes).
- Handles centering sentinels for `xpos`/`ypos` (`-1` center, `-2` center with offset approximation).

Quick start:
```bash
# From repo root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install pygame

# Run a sample GUI (e.g., main menu)
python pygame_gui_mvp.py extracted_by_go/guis/MAINMENU.GUI
```

Notes:
- This MVP uses simple shapes/colors (no GAF/PCX/palette yet).
- Next targets: resource loading (palettes, PCX/GAF), listbox/slider/text input handlers, save-under composition, and overlay/merge support.

