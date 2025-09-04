## Streaming Video Processing

Real-time video processing app built with Streamlit, OpenCV, and Clarifai. Ingest one or more videos from URLs or local files, run Clarifai models on frames, view overlays live, and export detections as JSON.

## Features

- Multiple inputs per run
	- Standard URLs: HTTP(S) files, HLS (.m3u8), RTSP
	- Local files: mp4, mov, mkv, avi
- Clarifai model selection
	- Authenticate with default or custom credentials (Base URL + PAT)
	- List models across all apps (or a single app) for the user
	- Per-video model selection with type-ahead filter
	- Configurable “Portal base host” for portal links (clarifai.com, dev.clarifai.com, custom)
- Smooth playback for live streams
	- Playback buffer (seconds) adds a constant latency to absorb jitter
	- Fixed max display FPS; drops excess frames to avoid bursts
	- 3s initial prebuffer with a clear “buffering…” state
- Flexible processing
	- Frame skip: run inference every N frames; draw last detections on all frames
	- Skip inference to verify decoding only
	- Stop Processing button
- Export detections
	- Download the last 100 detections per video as a single JSON file

## Supported sources

- HTTP(S) files: mp4, mov, mkv, avi (e.g., https://…/video.mp4)
- HLS live streams: .m3u8 (e.g., https://…/playlist.m3u8)
- RTSP cameras: rtsp://host:port/path (TCP transport)

Decoding uses OpenCV first (FFmpeg backend when available) and falls back to imageio (v3/v2) for HLS/RTSP and edge cases.

## Setup

Requirements:
- Python 3.9+ recommended
- Windows/macOS/Linux

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
streamlit run app.py
```

## Authentication (Clarifai)

Open the “Authentication (Clarifai)” expander in the app:
- Use default credentials from your environment, or toggle “Use custom credentials”.
- Provide Base URL (e.g., https://api.clarifai.com), User ID, optional App ID, and PAT.
- Portal base host controls where model links point (e.g., clarifai.com, dev.clarifai.com, or a custom domain).
- Click “Apply credentials” to reload with the new settings.

Model listing:
- If App ID is blank, the app lists models across all apps for the user.
- If necessary, provide an “App ID override” to list models from a specific app.
- Use “Refresh Models” after changing credentials/filters.

## Usage

1) Choose “Standard Video File URLs” or “Local Files”.
2) Provide inputs:
	 - URLs: one per line
	 - Local files: upload one or more files (saved to temp paths)
3) Adjust processing options:
	 - Frame skip (inference every N frames)
	 - Detection threshold
	 - Playback buffer (seconds) and Max display FPS
	 - Skip model inference (decode-only)
4) Select a Clarifai model for each video (use the filter box to narrow options).
5) Click “Process Videos”.
6) While running, click “Stop Processing” to end early.
7) Download detections: The “Download detections (JSON)” button is visible whenever recent detections exist.

## Buffering & latency

- The app maintains a constant playback delay equal to the “Playback buffer (seconds)” after an initial 3s prebuffer. This keeps playback smooth and prevents buffer drain.
- Max display FPS sets the render cadence; if your source FPS is lower, reduce this to help the buffer stay filled.
- For low-latency needs, set buffer to 0 (smoother playback may be reduced for bursty networks).

## Troubleshooting

- Windows decoding for files/HTTP: ensure you have `opencv-python` (not headless) to include FFmpeg codecs.
- Live streams stall or jitter: increase the playback buffer and/or lower max display FPS.
- RTSP issues: make sure your camera is reachable and TCP transport is allowed through firewalls.
- No video but JSON errors: enable “Skip model inference” to isolate decoding vs. model issues.
- No models listed: verify Clarifai credentials; use “App ID override” or “Refresh Models”.

## Project structure

- `app.py` — Streamlit entry point
- `pages/streaming_module.py` — main UI, video processing, buffering, and Clarifai integration

## License

See `LICENSE` for details.
