## Multimodal Input Helper

Use `scripts/multimodal_input.py` to send the same text + image payloads that the Streamlit app produces, but directly from your terminal. The script wraps `ClarifaiOpenAIClient`, so it shares the retry/backoff logic, metrics, and streaming callbacks.

```bash
export CLARIFAI_PAT="your_pat"
python scripts/multimodal_input.py \
  --image-url "https://samples.clarifai.com/cat1.jpeg" \
  --prompt "Describe what you see in this image."
```

Swap `--image-url` for `--image-path` when testing local files, and pass `--no-stream` if you prefer a single response payload. The script prints each streamed delta in real time followed by token/latency metrics, making it a quick way to validate multimodal requests outside the UI.

Looking for a ready-made scenario? `scripts/sample_product_inspection.py` issues the exact payload described in the JSON snippet (system + user instructions plus the image URL) so you can validate Clarifai's Gemini 2.5 Pro endpoint with one command.