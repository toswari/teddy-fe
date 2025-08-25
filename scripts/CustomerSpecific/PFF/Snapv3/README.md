# Football Snap Detection (CLI)

Lightweight computer-vision pipeline to locate the football snap frame in broadcast / coaching tape.
Uses Clarifai's unified detection model (filtered to player concepts), custom lightweight tracking, LOS (line of scrimmage) clustering, and robust motion heuristics (median/MAD baseline + absolute & derivative gates + sustain scoring + derivative fallback). Output artifacts include GIF(s) around the detected snap and motion / LOS velocity plots.


## Key Features
* Clarifai region detection with label filtering (singular/plural normalization)
* Optional SORT tracker (if `sort` module installed) or improved centroid tracker with velocity prediction & exponential smoothing
* LOS clustering via DBSCAN + PCA line refinement (focus on trench players)
* Robust snap heuristic (stability, calm-window, absolute motion, derivative spike, sustain, scoring + derivative fallback with onset backtracking)
* Automatic 200ms pre-offset adjustment for reaction time
* Detection caching (speeds reruns) keyed on path + mtime + size
* GIF creation & motion / LOS velocity visualization
* Configurable causal smoothing + formation-motion blending toggle + tracker smoothing strength

## Quick Start (Local)
```powershell
pip install -r requirements.txt
$env:CLARIFAI_PAT = "<your_personal_access_token>"
python main.py sample_videos/Play_01_Q0_SL_View1.mp4 -v
```
Outputs appear in `outputs/`.

## Environment Variables
| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `CLARIFAI_PAT` | Clarifai Personal Access Token | YES | (none) |
| `CLARIFAI_MODEL_URL` | Override model endpoint | NO | unified-model URL |

Create a `.env` if preferred.

## CLI Usage
```
python main.py <video_path> [--output outputs] [--gif-window 30] \
  [--verbose] [--debug-clarifai] [--no-cache] [--cache-dir cache] \
  [--min-los-cluster-size 8] [--min-active-los-players 6]
```

Important flags:
* `--debug-clarifai` – dump early concept names / boxes
* `--no-cache` – force fresh detections
* `--min-los-cluster-size` – required LOS cluster size
* `--min-active-los-players` – active moving LOS players threshold

## Advanced Tuning (constructor parameters)
| Param | Description |
|-------|-------------|
| `los_smooth_window` | Causal MA window (default 3) for LOS mean velocity |
| `use_formation_blend` | Blend wider formation motion (may over-smooth) |
| `tracker_smooth_alpha` | 0.3–0.95; higher = less smoothing |
| `snap_search_fraction` | Fraction of video for search window |
| `min_los_cluster_size` | Required LOS cluster size |
| `min_active_los_players` | Min moving LOS players |

## Output Artifacts
| File | Description |
|------|-------------|
| `<video>_snap.gif` | GIF around snap (± gif-window frames) |
| `<video>_motion.png` | Motion graph (player vs camera) |
| `<video>_motion_raw.png` | Unclipped raw (verbose mode) |
| `<video>_los_velocities.png` | LOS velocities distribution plot |
| `cache/detections_*.pkl` | Cached detections |

## Snap Time Heuristic
1. Gather LOS velocities per frame.
2. Causal smoothing (`los_smooth_window`).
3. Rolling median + MAD baseline (window up to 120 prior frames) with floor.
4. Candidate frames must pass stability, calm, absolute elevation, derivative, sustain checks.
5. Score candidates (derivative + sustain mean + active player count) and choose best.
6. Fallback derivative spike search if none pass.
7. Apply 200ms pre-offset.

## Caching
Delete `cache/` entry or use `--no-cache` when modifying detection filtering or model.

## Docker
Build:
```bash
docker build -t snap-detection .
```
Run (mount videos & supply PAT):
```bash
docker run --rm -e CLARIFAI_PAT=$CLARIFAI_PAT \
  -v $(pwd)/sample_videos:/app/sample_videos \
  -v $(pwd)/outputs:/app/outputs \
  snap-detection python3 main.py sample_videos/Play_01_Q0_SL_View1.mp4 -v
```
GPU:
```bash
docker run --gpus all --rm -e CLARIFAI_PAT=$CLARIFAI_PAT \
  -v $(pwd)/sample_videos:/app/sample_videos \
  -v $(pwd)/outputs:/app/outputs \
  snap-detection python3 main.py sample_videos/Play_01_Q0_SL_View1.mp4
```
Compose:
```bash
docker-compose run --rm snap-detection python3 main.py sample_videos/Play_01_Q0_SL_View1.mp4
```

## Structure (trimmed)
```
main.py
snap_detector.py
requirements.txt
Dockerfile / docker-compose.yml
sample_videos/
outputs/
cache/
```

## Known Limitations
* Requires relatively stable sideline / elevated view.
* Pre-snap shifts / motion men can delay detection; relax thresholds if too late.
* Clarifai network latency; mitigated by caching.

## Troubleshooting
| Symptom | Suggestion |
|---------|------------|
| Early spike missed | Lower `min_active_los_players`; set `use_formation_blend=False` |
| Too smooth / late | Reduce `los_smooth_window` (2); increase `tracker_smooth_alpha` (0.9) |
| Jittery tracks | Lower `tracker_smooth_alpha` (0.6) |
| No snap detected | Lower `min_los_cluster_size` |
| Many unstable rejects | Reduce both LOS thresholds slightly |

## Next Ideas
* Expose tuning flags via CLI.
* Unit tests with synthetic LOS signals.


---
Enjoy analyzing snaps!
