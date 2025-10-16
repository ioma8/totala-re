# TotalA Reverse Engineering (totala-re)

Rapid reverse engineering of Total Annihilation’s engine with emphasis on HPI resource archives and runtime subsystems.

## Goals
- Document the original Windows engine architecture and data flow well enough to guide a clean-room reimplementation (targeting Rust).
- Provide reliable tooling for unpacking game assets, validating extracted data, and converting proprietary formats (SQSH, TMH/F) into modern equivalents.
- Share progressive findings in a structured way so additional contributors can extend the work (AI, networking, rendering, etc.).

## Current Artefacts
- **Docs** – `RAPID_ANALYSIS.md`, `ANALYSIS_PLAN.md`, `HPI_PARSER_COMPLETE.md`, `PROGRESS_SUMMARY.md` capture the ongoing findings.
- **Tools** – `hpi_parser.py`, `extracted_files_checker.py`, `tmhf_to_wav.py` support archive extraction, validation, and audio conversion.
- **Status** – HPI/SQSH formats decoded, TMH audio normalised, groundwork laid for engine reimplementation.
