# Clarifai's PFF working repo
## Getting Started
1. This project uses `uv` and `make`, so make sure those are installed
1. We also make use of `git-lfs` for versioning of model files (e.g., pytorch files, onnx files, scikit-learn files)
   so you need to configure git-lfs
   1. `brew install git-lfs`
   2. `git lfs install`
1. `uv sync`

## Structure
- `config/` - some useful configurations / hyper-parameter sets
- `deploy/` - anything deployment related (e.g., runner file trees)
- `scripts/` - some useful scripts for mot eval, tuning, plotting
- `src/clarifai_pff/` - source tree for the package, importable by runners due to `make` recipes
- `tests/` - directory for tests
- `utils/` - some utilities
- `Makefile` - Makefile for repeatable tasks (e.g., preflight local docker builds, deployments)

## Training ReID
1. Generate data in protobuf format for ground truth and detection / embeddings in separate folders
1. `make reid DB_FOLDER=<> GT_FOLDER=<>`