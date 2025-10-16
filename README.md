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
