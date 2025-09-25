# Any-to-Any Clarifai Runner

A clean, minimal any-to-any Clarifai local runner model that accepts multiple input types
(Video, Image, Text, Audio) and returns proper Clarifai objects with bytes for chaining.

---

## ✨ Features

- **Any-to-Any Processing**: Accepts Video, Image, Text, or Audio inputs
- **Proper Clarifai Objects**: Returns Image objects with bytes (not JSON strings)
- **URL Downloading**: Automatically downloads URLs to actual bytes for chaining
- **Multiple Processing Methods**:
  - `predict` – Single input processing
  - `batch_predict` – Process multiple inputs concurrently 
  - `generate` – Streaming processing with status updates
  - `stream` – Batch streaming for multiple requests
- **Chaining Support**: Output objects work seamlessly with other Clarifai models
- **Docker Ready**: Containerized with minimal dependencies

---

## 📦 Project Structure

```
any-to-any/
├── 1/
│   └── model.py            # Any-to-any model
├── Dockerfile              # Container setup
├── docker-compose.yml      # Local orchestration
├── requirements.txt        # Minimal dependencies
├── config.yaml            # Model configuration
├── start_runner.sh         # Clarifai auth + runner startup
└── README.md               # This documentation
```

---

## 🚀 Quick Start

1. Copy `env.example` to `.env` and fill in ALL required variables:
```
CLARIFAI_PAT=your_pat_here
CLARIFAI_USER_ID=your_user_id
CLARIFAI_APP_ID=your_app_id
CLARIFAI_MODEL_ID=any-to-any-model
CLARIFAI_MODEL_TYPE_ID=any-to-any
CLARIFAI_DEPLOYMENT_ID=your_deployment_id
CLARIFAI_COMPUTE_CLUSTER_ID=your_compute_cluster_id
CLARIFAI_NODEPOOL_ID=your_nodepool_id
LOG_LEVEL=INFO
```
If any are missing, the startup script exits with an error.

2. Build & run:
```powershell
docker-compose up --build -d
```

3. View logs:
```powershell
docker logs any-to-any-runner
```

4. Use the model via Clarifai SDK (replace URL/deployment IDs per your workspace):
```python
from clarifai.client import Model
from clarifai.runners.utils.data_utils import Image, Video

model = Model("https://clarifai.com/your-user/your-app/models/any-to-any-model", deployment_id="local-runner-deployment")

# Process an image URL - returns Image object with bytes
result = model.predict(
    image="https://samples.clarifai.com/metro-north.jpg",
    operation="process"
)

# Process video input - returns Image object  
result = model.predict(
    video="https://example.com/video.mp4",
    operation="analyze"
)

# Process text input
result = model.predict(
    text="Generate an image from this text",
    operation="generate"
)
```

---

## 🧪 Local Dev (without container)

```powershell
cd 1
python model.py
```

---

## 📥 Input Types & Parameters

### Supported Inputs
| Input Type   | Description                              | Example                                      |
|--------------|------------------------------------------|----------------------------------------------|
| Image        | Image URL or Clarifai Image object      | `"https://example.com/image.jpg"`           |
| Video        | Video URL or Clarifai Video object      | `"https://example.com/video.mp4"`           |
| Text         | Plain text string                        | `"Process this text"`                       |
| Audio        | Audio URL or identifier                  | `"https://example.com/audio.wav"`           |

### Processing Parameters
| Parameter    | Type   | Description                             | Default      |
|--------------|--------|-----------------------------------------|--------------|
| output_type  | string | Output format (image, video, text, audio) | `"image"`    |
| operation    | string | Processing operation                    | `"process"`  |

### Operation Types
- `"process"` - Basic processing/conversion
- `"describe"` - Generate description or analysis  
- `"analyze"` - Detailed analysis of input

---

## 🔍 Sample Outputs

### Predict Response:
Returns a proper Clarifai `Image` object with bytes attribute:
```python
# The model returns Image objects like this:
Image(bytes=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...')
```

This allows seamless chaining with other Clarifai models:
```python
# Chain models together
result1 = model1.predict(text="Generate an image")
result2 = model2.predict(image=result1)  # Uses bytes from result1
```

### Generate Stream Response:
```
Step 1/3: Validating image input
Step 2/3: Processing image with operation: process  
Step 3/3: Processing complete
```

### Method Parameters:

| Method | Parameters | Description |
|--------|------------|-------------|
| **predict** | `video`, `image`, `text`, `audio`, `operation`, `output_type` | Single input processing |
| **batch_predict** | `videos[]`, `images[]`, `texts[]`, `audios[]`, `operation`, `output_type` | Batch processing |  
| **generate** | `video`, `image`, `text`, `audio`, `operation`, `steps` | Streaming with progress |
| **stream** | `input_iterator`, `batch_size` | Process multiple requests |

---

## 🛠 Extending

1. Modify input processing logic in `model.py`
2. Add custom operations for different input types
3. Extend return types to support Video, Text, or Audio outputs
4. Add custom URL downloading or preprocessing
5. Rebuild the container after changes: `docker-compose build`

### Environment Variables (Strict)
The runner does NOT invent defaults. Provide everything in `.env`:

| Variable | Purpose |
|----------|---------|
| CLARIFAI_PAT | Auth token (personal access token) |
| CLARIFAI_USER_ID | Your Clarifai user/account id |
| CLARIFAI_APP_ID | App namespace for the model |
| CLARIFAI_MODEL_ID | Model identifier (e.g. any-to-any-model) |
| CLARIFAI_MODEL_TYPE_ID | Model type: **any-to-any** |
| CLARIFAI_DEPLOYMENT_ID | Deployment id mapping model version to compute |
| CLARIFAI_COMPUTE_CLUSTER_ID | Compute cluster id (created if absent) |
| CLARIFAI_NODEPOOL_ID | Nodepool id within the cluster |
| LOG_LEVEL | (Optional) Script logging verbosity |

### Dependencies
The Docker image includes minimal dependencies:
- clarifai - Clarifai SDK and runner framework
- requests - URL downloading
- pydantic - Data validation  
- python-dotenv - Environment configuration

---

## 🔐 Security Notes

- PAT is injected via `.env` (do not commit your real credentials).
- This baseline performs no network calls besides Clarifai runner operations unless you add them.
- Remove unused env vars if you fork from a template that included more (e.g., AWS_*).

---

## ❓ Troubleshooting

| Issue | Check |
|-------|-------|
| Container exits immediately | Is `CLARIFAI_PAT` set? Correct user ID? Model type set to `any-to-any`? |
| URL download fails | Check URL accessibility and format |
| Processing errors | Verify input format is supported (Image, Video, Text, Audio) |
| Chaining issues | Ensure output Image objects have bytes attribute set |

View logs:
```powershell
docker logs -f any-to-any-runner
```

---

## 📤 Sharing / Forking

- Replace the model namespace (user/app/model) in examples with your own.
- Update LICENSE if you need a different one (currently MIT).
- Add tests or CI as your project grows.

---

## 📄 License

MIT – see `LICENSE` for details.

---

## 🎯 Use Cases

- **Model Chaining**: Pass outputs between different Clarifai models
- **Cross-modal Processing**: Convert between different input types (text→image, video→image)
- **URL Processing**: Download and process remote media files
- **Batch Processing**: Handle multiple inputs efficiently  
- **Streaming Workflows**: Real-time processing with progress updates
- **Development Template**: Base for building custom any-to-any models

## 🙌 Attribution  

Clean any-to-any model template built on the Clarifai Local Runner framework, optimized for chaining and cross-modal processing.
