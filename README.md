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

### Extracting HPI Archives
```bash
# List archive contents (console view)
python3 hpi_parser.py totala1.hpi --list

# Extract everything into ./extracted
python3 hpi_parser.py totala1.hpi --extract-all extracted

# Extract a single file
python3 hpi_parser.py totala1.hpi --extract "path/to/file.txt" output.txt
```

### Validating Extracted Files
```bash
# Sanity-check extracted assets
python3 extracted_files_checker.py extracted
```

### Converting Audio Files
```bash
# Convert TMH/TMHF audio to WAV
python3 tmhf_to_wav.py extracted/sounds converted_wav
```

### Assembling HPI Archives
The HPI assembler now properly builds archives from extracted directories without requiring the original HPI file:

```bash
# Assemble HPI from extracted directory (using zlib compression)
python3 hpi_assembler.py extracted rebuilt.hpi

# Assemble with specific compression mode (0=none, 1=LZ77, 2=zlib)
python3 hpi_assembler.py extracted rebuilt.hpi --compression 2

# Assemble with encryption (key 0-255)
python3 hpi_assembler.py extracted rebuilt.hpi --key 42

# Validate against original (optional)
python3 hpi_assembler.py extracted rebuilt.hpi --reference totala1.hpi

# Verify hashes match if bit-identical
shasum -a 256 totala1.hpi rebuilt.hpi
```

**Note:** The assembler creates proper HPI archives from scratch by:
- Building directory structures from the filesystem
- Compressing files using SQSH chunks (supports modes 0/1/2)
- Generating chunk tables
- Encrypting data with position-dependent XOR cipher
- Writing complete HPI file with proper headers and metadata

The assembled archives are fully compatible with the parser and the original Total Annihilation engine.

### Testing the HPI Assembler
```bash
# Run comprehensive round-trip tests
python3 test_hpi_roundtrip.py
```

Temporary outputs (e.g. `extracted/`, `converted_wav/`, `rebuilt.hpi`) can be removed after verification.
