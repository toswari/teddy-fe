# Clarifai Token Estimator Streamlit App

Interact with Clarifai's OpenAI-compatible text models **or** Clarifai's native Gemini 2.5 Pro generate() flow, stream completions, and capture prompt/output token counts alongside latency metrics.

**Implementation Note:** This application follows Clarifai's official OpenAI-compatible API patterns, using the `openai` Python client with `base_url="https://api.clarifai.com/v2/ext/openai/v1"` and `max_tokens` parameter as documented in Clarifai examples.

## Features
- Streamlit UI with sidebar configuration for Clarifai PAT, base URL, and region hints.
- Manual Clarifai model URL entry (e.g., `https://clarifai.com/.../versions/...`).
- Optional image uploader that embeds the selected image alongside the text prompt for multimodal inference.
- Optional system message field plus remote image URL input for parity with Clarifai's OpenAI payloads (upload or link).
- Quick preset picker to load sample system/prompt combos (product QA, simple chat) with one click.
- **Inference mode toggle:** choose between OpenAI-compatible `chat.completions` (GPT-4o/GPT-5.1) and the native Gemini `generate()` helper, which aggregates streaming chunks and estimates tokens (including size-based image overhead) via [clarifai_token_estimator/gemini_generate.py](clarifai_token_estimator/gemini_generate.py).
- Streaming or non-streaming completions with persistent response view.
- Metrics reporting: input/output tokens, time-to-first-token (TTFT), total API time.
- Diagnostics + debug panels showing attempt metadata plus raw request/response payloads.
- Resilient client with retry/backoff for transient errors.
- Optional config defaults for prompt text and model URL lists (via `.streamlit/app-settings.toml`).

## Prerequisites
- Python 3.12+
- Clarifai account with OpenAI-compatible access and API key.

## Setup
1. Run the setup script to create and configure the virtual environment.

```bash
./setup-env.sh
```

This script will:
- Check for Python 3.12
- Create a virtual environment
- Install all required dependencies

2. Provide Clarifai credentials via environment variables or `streamlit` secrets:
   - `CLARIFAI_PAT`
   - `CLARIFAI_BASE_URL` (e.g. `https://api.clarifai.com/v2/ext/openai/v1`)
   - `CLARIFAI_PREFERRED_REGION` (optional)

Create `.streamlit/secrets.toml` if you prefer local secrets:

```toml
CLARIFAI_PAT = "your-personal-access-token"
CLARIFAI_BASE_URL = "https://api.clarifai.com/v2/ext/openai/v1"
CLARIFAI_PREFERRED_REGION = "us-east-1"
```

## Run the App

### Quick Start
```bash
./start.sh
```

This will start the Streamlit app on http://localhost:8501.

### Manual Start
If you prefer to start manually:

```bash
source .venv/bin/activate
streamlit run app.py
```

### Stop the App
```bash
./stop.sh
```

This will gracefully stop the running Streamlit app.

## Usage
1. Paste the full Clarifai model URL (example shown in the placeholder) or pick one from the dropdown.
2. Pick a preset (optional) and tweak the system message/prompt as needed.
3. Choose the inference pathway:
   - **OpenAI-compatible** (default) keeps streaming GPT-4o/GPT-5.1 responses through Clarifai's `/ext/openai` endpoint.
   - **Gemini native generate()** calls Clarifai's Gemini 2.5 Pro deployment using the helper in [clarifai_token_estimator/gemini_generate.py](clarifai_token_estimator/gemini_generate.py); the PAT is reused directly and the app auto-defaults to `https://clarifai.com/gcp/generate/models/gemini-2_5-pro` if no model is specified.
4. Provide an image by uploading a file or pasting a public `Image URL` (both modes support multimodal input).
5. Adjust generation parameters in the sidebar and click **Run Inference**.
6. Review streamed output, metrics, diagnostics, and the raw request/response data in the UI or terminal.

### Gemini Native Mode
- Requires only `CLARIFAI_PAT`; the base URL text box is ignored while this mode is active.
- The helper aggregates streaming chunks, measures TTFT/total latency, and estimates tokens using `tiktoken` plus an image-size heuristic (1 KB ≈ 1 token, bounded between 85 and 4096 prompt tokens per image).
- Uploaded image bytes are preferred so we can calculate precise token estimates, but URL-only inputs still incur the minimum overhead.

### Optional App Configuration
Add defaults to `.streamlit/app-settings.toml` to speed up testing:

```toml
[app]
default_system_prompt = "You are a helpful assistant that inspects product photos."
default_prompt = "Analyze the attached image and list 3 visual improvements."
default_image_url = "https://example.com/path/to/image.jpg"
model_urls = [
   "https://clarifai.com/gcp/generate/models/gemini-2_5-pro/versions/cee9e1e14e8e41c0b39e4223a12d7854",
   "https://clarifai.com/openai/chat-completion/models/gpt-4.1-mini",
]
```

The prompt text area initializes with `default_prompt`, and the select box lists each `model_urls` entry (manual overrides still supported).

## CLI Multimodal Example

Need a quick smoke test without the Streamlit UI? Use the helper script that mirrors the same Clarifai wiring:

```bash
CLARIFAI_PAT=your_pat \
python scripts/multimodal_input.py \
   --image-url "https://samples.clarifai.com/cat1.jpeg" \
   --model-url "https://clarifai.com/openai/chat-completion/models/gpt-4o"
```

Pass `--image-path` for local files, tweak prompt/generation flags (for example `--no-stream`), and the script will print streamed output plus token/latency metrics in the terminal.

### Gemini 2.5 Pro Example

To call Gemini through the native generate() helper (with size-aware token estimation) run:

```bash
CLARIFAI_PAT=your_pat PYTHONPATH=. python scripts/gemini-pro-example.py
```

The script loads `sample.png`, prints its byte/MB size, shows TTFT/total time, and displays estimated prompt/completion tokens exactly like the Streamlit Gemini mode.

### Product Photo Inspection Sample

The JSON snippet you shared is now baked into `scripts/sample_product_inspection.py`, which uses Clarifai's OpenAI-compatible client with the Gemini 2.5 Pro slug:

```bash
CLARIFAI_PAT=your_pat \
python scripts/sample_product_inspection.py \
   --image-url "https://example.com/path/to/image.jpg"
```

Override `--system`, `--prompt`, or `--model-url` as needed; the script prints the assistant's response exactly as returned by the API.

### Simple Text Chat Example

For the most basic Clarifai/OpenAI-compatible request (system + user message, no images), run:

```bash
CLARIFAI_PAT=your_pat \
python scripts/simple_chat_completion.py \
   --system "You are a helpful assistant." \
   --user "Who are you?"
```

Pass `--no-stream` if you prefer the non-streaming response payload.

### Structured Output Example

For structured JSON output using Pydantic schemas with `response_format` (matching Clarifai's official example pattern):

```bash
CLARIFAI_PAT=your_pat \
python scripts/structured_output_example.py
```

This demonstrates the recommended approach for extracting structured data from Clarifai models using JSON Schema validation.

## Testing

Run unit tests (no API calls required):

```bash
PYTHONPATH=. pytest tests/test_clarifai_client.py tests/test_metrics.py -v
```

Run integration tests with live Clarifai API (requires `CLARIFAI_PAT`):

```bash
CLARIFAI_PAT=your_pat \
PYTHONPATH=. pytest tests/test_integration_*.py -v -s
```

Or use the convenience script:

```bash
CLARIFAI_PAT=your_pat ./run_integration_tests.sh
```

The integration tests in [tests/test_integration_image_description.py](tests/test_integration_image_description.py) now cover both inference pathways end-to-end:
- **`test_gpt4o_image_description_with_sample_png`** ✅ - Local [sample.png](sample.png) with GPT-4o (OpenAI-compatible).
- **`test_gpt4o_streaming_image_description`** ✅ - Streaming GPT-4o run with incremental TTFT tracking.
- **`test_remote_image_url_description`** ✅ - Uses a remote cat image URL with GPT-4o via Clarifai's OpenAI layer.
- **`test_gemini_pro_image_with_native_sdk`** ✅ - Exercises the Gemini generate() helper with URL/byte inputs, validating the image token estimation flow.
- **`test_gpt51_text_completion`** ✅ - Simple text-only GPT-5.1 regression.

All tests follow the exact pattern:
```python
from openai import OpenAI
import base64

client = OpenAI(
    base_url="https://api.clarifai.com/v2/ext/openai/v1",
    api_key=os.environ["CLARIFAI_PAT"]
)
```

## Notes
- Time-to-first-token is calculated from first streamed delta; enable *Stream Responses* for TTFT accuracy.
- Token counts rely on Clarifai `usage` payload when available; otherwise `tiktoken` estimates are used and labelled as such.
- Avoid committing secrets. The app stores sensitive values only in `st.session_state` for the active session.
