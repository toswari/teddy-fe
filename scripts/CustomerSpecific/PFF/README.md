# Clarifai's PFF working repo
## Getting Started
1. This project uses `uv` and `make`, so make sure those are installed
1. `uv sync`

## Structure
- `config/` - some useful configurations / hyper-parameter sets
- `deploy/` - anything deployment related (e.g., runner file trees)
- `scripts/` - some useful scripts for mot eval, tuning, plotting
- `src/clarifai_pff/` - source tree for the package, importable by runners due to `make` recipes
- `tests/` - directory for tests
- `utils/` - some utilities
- `Makefile` - Makefile for repeatable tasks (e.g., preflight local docker builds, deployments)