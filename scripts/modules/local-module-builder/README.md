 # build_module.py — Local Module Builder for Clarifai Streamlit Apps

Build and optionally run a Docker image for a Streamlit module locally, mirroring the Clarifai Module Manager container pattern. Useful for fast iteration without GitHub.

## Quick start (Windows PowerShell)

Prerequisites:
- Docker Desktop installed and running
- A Streamlit app folder with `app.py` and `requirements.txt`

Example:

```powershell
# Build and run on localhost:8501
python .\build_module.py C:\path\to\your\streamlit_app
```

Then open http://localhost:8501

## Required/optional app files

Required in your app directory:
- app.py — Streamlit entrypoint
- requirements.txt — Python dependencies

Optional:
- .streamlit/secrets.toml — merged with any `--secret` CLI values
- README.md — app docs
- assets/ — static files

## What the script does

- Validates the app directory (requires `app.py` + `requirements.txt`).
- Creates a temporary build context and generates:
  - Dockerfile (Python 3.12-slim; uses uv for env + pip install)
  - .dockerignore
  - .streamlit/secrets.toml (if `--secret` provided)
- Builds the Docker image (unless `--no-build`).
- Optionally exports the image to tar/tar.gz (`--export`, `--compress-export`).
- Runs the container mapping host port -> 8501 (unless `--no-run`).
- Debug mode starts a bash shell as entrypoint.

## Usage

```powershell
python .\build_module.py <app_path> [options]
```

Options:
- --image, -i            Docker image name (default: clarifai-module-{dirname})
- --port, -p             Host port to expose (default: 8501)
- --no-build             Only generate Dockerfile/.dockerignore; don’t build
- --no-run               Build image but don’t run a container
- --debug                Start container with bash shell (for debugging)
- --env, -e KEY=VALUE    Add env var (repeatable)
- --secret, -s KEY=VALUE Add Streamlit secret (repeatable)
- --clarifai-user-id     Convenience for both env and secret: CLARIFAI_USER_ID
- --clarifai-pat         Convenience for both env and secret: CLARIFAI_PAT
- --clarifai-app-id      Convenience for both env and secret: CLARIFAI_APP_ID
- --export, -x PATH      Export built image to PATH (e.g., my-image.tar)
- --compress-export      Gzip the export (use with .tar.gz)

Env vars vs secrets:
- Env vars (`-e/--env`) are visible to the process in the container.
- Streamlit secrets (`-s/--secret`) are accessible via `st.secrets["KEY"]` in your app.

## Examples

```powershell
# Build and run a module
python .\build_module.py C:\apps\my_streamlit_app

# Build with Clarifai credentials
python .\build_module.py C:\apps\my_app --clarifai-user-id YOUR_USER --clarifai-pat YOUR_PAT

# Custom secrets and env vars
python .\build_module.py C:\apps\my_app -s API_KEY=secret123 -e DEBUG=true -e LOG_LEVEL=info

# Custom image name and port
python .\build_module.py C:\apps\my_app --image my-module --port 8502

# Build but do not run
python .\build_module.py C:\apps\my_app --no-run

# Only generate Dockerfile/.dockerignore (no build)
python .\build_module.py C:\apps\my_app --no-build

# Export image
python .\build_module.py C:\apps\my_app --export C:\tmp\my-module.tar

# Export compressed image
python .\build_module.py C:\apps\my_app --export C:\tmp\my-module.tar.gz --compress-export

# Debug mode (open bash in the container)
python .\build_module.py C:\apps\my_app --debug
```

## Container configuration

- Base: python:3.12-slim (public ECR)
- Non-root user `python` (uid 999)
- `uv venv .venv && uv pip install -r requirements.txt`
- Streamlit server on 0.0.0.0:8501, usage stats disabled
- Healthcheck: `http://localhost:8501/healthz`
- Entrypoint runs `streamlit run app.py` using the venv’s Python

## Export and load images

- Uncompressed tar:
  - Save: `--export C:\path\my-image.tar`
  - Load: `docker load -i C:\path\my-image.tar`
- Compressed tar.gz:
  - Save: `--export C:\path\my-image.tar.gz --compress-export`
  - Load: `gunzip -c C:\path\my-image.tar.gz | docker load`

## Troubleshooting

- Docker not found/running
  - Start Docker Desktop; `docker --version` should work in PowerShell.

- Port already in use
  - Use another port: `--port 8502`.

- Build fails on native deps (Pillow/OpenCV/etc.)
  - Base image installs common libs (libjpeg/libpng/etc.). If you still see errors, adjust your app’s deps or extend the Dockerfile accordingly.

- Windows paths with spaces
  - Quote the path: `python .\build_module.py "C:\\path with space\\app"`

## Cleanup

```powershell
# Stop/remove container and delete image (default name pattern shown)
$img = "clarifai-module-<your-app-dir>";
docker rm -f "$($img)-container" 2>$null;
docker rmi $img
```

## Security

- Don’t hardcode secrets into your repo. Prefer `--secret` at build/run time.
- `--debug` opens a shell; avoid on untrusted images.

## License

See `LICENSE` in the repo root.
