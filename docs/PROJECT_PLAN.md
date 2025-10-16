# Project Plan & Status

## Mission
Fully document and modernise the Total Annihilation runtime so that a faithful, open reimplementation (targeting Rust) becomes feasible. The focus areas are engine behaviour, data formats, and tooling for working with original assets.

## Achievements to Date
- Phase 1 (architecture survey) complete: startup flow, scheduler and message loop mapped.
- HPI archive format fully specified, including SQSH chunk compression and TMH/TMHF audio wrappers.
- Python tooling delivers end-to-end extraction, validation, and WAV conversion of original assets.
- Windows/DirectX API usage, global structures, and key function groups catalogued for later reimplementation.

## Active Focus
1. **Data structures** – expand the map of `0x511de8` and related global state blocks.
2. **Subsystem deep dives** – graphics/audio initialisation, AI, networking, and save/load paths.
3. **Rust toolchain** – prepare a reference HPI reader and supporting crates based on the proven Python logic.

## Backlog
- Reverse engineer unit/weapon runtime structures and serialisation.
- Document multiplayer protocol and lobby flow.
- Capture DirectDraw/DirectSound configuration details for compatibility shims.
- Draft contributor guidelines and coding standards for future Rust work.

## Reference Timeline
| Phase | Scope | Status |
| ----- | ----- | ------ |
| 1 | Architecture & call graph mapping | ✅ Complete |
| 2 | Data structures & resources | ⏳ In progress |
| 3 | Subsystem deep dives (graphics, AI, networking, audio) | ▶ Pending |
| 4 | Algorithm analysis (pathfinding, physics, simulation) | ▶ Pending |
| 5 | Documentation polish & reimplementation hand-off | ▶ Pending |

Progress updates and deeper technical notes live in the companion documents under `docs/`.
