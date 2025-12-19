![Clarifai logo](https://www.clarifai.com/hs-fs/hubfs/logo/Clarifai/clarifai-740x150.png?width=240)

# Clarifai Demo - DAM / Personalization

UI module to help demonstrate some of the Clarifai capabilities around Digital Asset Management and Content Personalization# module-dam-and-personalization
# module-dam-and-personalization

## Setup

### Option 1: Docker (Recommended)

**Prerequisites:**
- Docker installed on your system
- Clarifai credentials (PAT, User ID, App ID)

**Quick Start:**

1. Create your `.streamlit/secrets.toml` file:
```bash
mkdir -p .streamlit
cat > .streamlit/secrets.toml <<EOF
CLARIFAI_PAT = "your_personal_access_token_here"
CLARIFAI_USER_ID = "your_user_id"
CLARIFAI_APP_ID = "your_app_id"
EOF
```

2. Build and run with the provided script:
```bash
./docker-build.sh
```

The app will be available at `http://localhost:8501`

**Using Docker Compose (Easiest):**

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

**Alternative Docker Commands:**

Build the image:
```bash
docker build -t clarifai-dam-demo .
```

Run with secrets file (recommended):
```bash
docker run -d \
  --name clarifai-dam-demo \
  -p 8501:8501 \
  -v "$(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro" \
  clarifai-dam-demo:latest
```

Or run with environment variables:
```bash
docker run -d \
  --name clarifai-dam-demo \
  -p 8501:8501 \
  -e CLARIFAI_PAT="your_pat" \
  -e CLARIFAI_USER_ID="your_user_id" \
  -e CLARIFAI_APP_ID="your_app_id" \
  clarifai-dam-demo:latest
```

**Useful Docker Commands:**
```bash
# View logs
docker logs -f clarifai-dam-demo

# Stop container
docker stop clarifai-dam-demo

# Restart container
docker restart clarifai-dam-demo

# Remove container
docker rm -f clarifai-dam-demo
```

### Option 2: Local Development

**Install dependencies with pip:**
```bash
pip install -r requirements.txt
```

**Or with Conda (recommended for development):**
```bash
conda env create -f environment.yml
conda activate dam-312
```

**Configure secrets:**
Create `.streamlit/secrets.toml` with your Clarifai credentials:
```toml
CLARIFAI_PAT = "your_personal_access_token_here"
CLARIFAI_USER_ID = "your_user_id"
CLARIFAI_APP_ID = "your_app_id"
```

**Start the app:**
```bash
./start.sh
```

The app will be available at `http://localhost:8501`

**Stop the app:**
```bash
./stop.sh
```

## Technical Notes

- Uses Clarifai SDK `>=11.12.1` and `clarifai-grpc>=11.11.4`
- Compatible with `protobuf>=5` to avoid deprecated APIs
- Python 3.12 runtime
- Debug logging enabled for API calls (console output)

## Verifying Deployment

**Check if the container is running:**
```bash
docker ps | grep clarifai-dam-demo
```

**Verify port mapping:**
```bash
docker port clarifai-dam-demo
# Should show: 8501/tcp -> 0.0.0.0:8501
```

**Access the application:**
- Open your browser to: `http://localhost:8501`
- Or use curl to test: `curl -I http://localhost:8501`

**View logs:**
```bash
# Docker Compose
docker-compose logs -f

# Docker command
docker logs -f clarifai-dam-demo
```

## Troubleshooting

**Port Mapping Not Visible in Docker Desktop:**
Even if Docker Desktop UI doesn't show the port, verify with the command line:
```bash
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep clarifai-dam-demo
```
If you see `0.0.0.0:8501->8501/tcp`, the port is correctly mapped.

**Model Restrictions:**
Some models require dedicated compute and may not work on shared infrastructure. If you see an error like "Model is restricted to dedicated compute only", try selecting a different model from the dropdown.

**Empty Model Lists:**
If no models appear in the dropdown, verify your Clarifai credentials in `.streamlit/secrets.toml` and check the console output for authentication errors.

**Cannot Access Application:**
1. Verify the container is running: `docker ps | grep clarifai-dam-demo`
2. Check port mapping: `docker port clarifai-dam-demo`
3. Ensure no other service is using port 8501: `lsof -i :8501`
4. Check container logs for errors: `docker logs clarifai-dam-demo`
