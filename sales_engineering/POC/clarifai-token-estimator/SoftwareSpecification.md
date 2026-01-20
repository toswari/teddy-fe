# Clarifai Token Estimator – Streamlit App Specification

## Overview
Build a Streamlit web application that lets users select text-generation models available on Clarifai via its OpenAI-compatible API, enter a prompt, and receive a text response along with detailed metrics: input tokens, output tokens, time-to-first-token (TTFT), and total API time. The app emphasizes streaming for accurate TTFT measurement and provides robust logging for diagnostics.

## Goals
- Provide a simple UI to choose Clarifai models and run prompts.
- Use OpenAI-compatible client settings to call Clarifai inference.
- Display response text and metrics (tokens, TTFT, total time).
- Offer resilience (retries, graceful errors) and actionable diagnostics.

## Scope
Included:
- Model discovery (list models or allow manual entry).
- Prompt execution (non-stream and stream modes; stream preferred for TTFT).
- Metrics capture: prompt and completion tokens, TTFT, total API time.
- Basic parameter controls: `temperature`, `max_completion_tokens`, `top_p`.
- Authentication via Clarifai API key and configurable base URL.
Excluded (Phase 1):
- Image/audio modalities, function calling, tool use.
- Conversation history management and persistence.
- Role-based access, multi-user tenancy.

## User Stories
- As a user, I can select a Clarifai text model and run a prompt.
- As a user, I can see input/output token counts, TTFT, and total time.
- As a user, I can adjust generation parameters and re-run quickly.
- As a user, I can fall back to manual model entry if listing fails.

## Functional Requirements
### Model Selection
- Display a dropdown of available Clarifai text-generation models.
- If the model list API is unavailable, show a text field to enter a model ID.
- Persist last-used model in session state.

### Prompt Execution
- Execute completion requests via OpenAI-compatible Clarifai endpoint.
- Support streaming responses to measure TTFT. Non-stream mode is optional.
- Configurable parameters: `temperature` (0.0–2.0), `max_completion_tokens` (50–4096, model-dependent), `top_p` (0–1), `presence_penalty`, `frequency_penalty` (if supported).

### Metrics & Telemetry
- Capture and display:
	- Input tokens (`prompt_tokens`).
	- Output tokens (`completion_tokens`).
	- TTFT: elapsed time from request start to first streamed token.
	- Total API time: elapsed time from request start to final token/response end.
- Prefer API-provided `usage` fields; fallback to local estimation if missing.
- Show a collapsible diagnostics panel (request ID, status code, timing breakdown).

### Error Handling & Retries
- Gracefully handle auth failures, rate limits (429), timeouts, and server errors.
- Implement exponential backoff for transient errors (e.g., 429, 5xx).
- Display human-readable errors and a link to diagnostics.

## Non-Functional Requirements
- Reliability: Retry transient failures with capped backoff.
- Performance: Streaming enabled by default for TTFT accuracy.
- Usability: Minimal clicks; clear metrics; accessible components.
- Observability: Structured logs with request and timing metadata.
- Security: API key never logged; stored only in environment/Streamlit secrets.

## UI/UX
### Layout
- Sidebar: Authentication and configuration (API key, base URL, region).
- Main: 
	- Controls: Model selector, parameters, prompt textarea, Run button.
	- Output: Streamed response text area.
	- Metrics: Cards or table showing tokens, TTFT, total time.
	- Diagnostics: Expandable section with raw metadata.

### Components
- Model Selector: Dropdown populated from Clarifai; text input fallback.
- Prompt Input: Multi-line textarea with character count.
- Parameters: Sliders/inputs for `temperature`, `max_completion_tokens`, `top_p`.
- Run Button: Triggers streaming request; disables while running.
- Results Panel: Live stream render; final response preserved in session.
- Metrics Panel: 
	- Input tokens, Output tokens, TTFT (ms), Total time (ms).
- Diagnostics Panel: 
	- Status code, request IDs, region, attempt count, timing breakdown.

## Architecture
### Tech Stack
- Python 3.10+
- Streamlit for UI
- OpenAI Python SDK (1.x) configured for Clarifai-compatible endpoint
- `tiktoken` (or equivalent) for token estimation fallback
- `requests` for model listing if separate API is required

### High-Level Flow
1. App starts; reads `CLARIFAI_API_KEY` and `CLARIFAI_BASE_URL` from environment or Streamlit secrets.
2. Attempts to fetch model list (text-generation capable) from Clarifai.
3. User selects model, enters prompt and parameters.
4. App sends a streaming completion request via OpenAI client (base URL overridden).
5. Measures TTFT (first chunk arrival) and total time (final chunk processed).
6. Displays response text and metrics; logs diagnostics.

## Clarifai OpenAI-Compatible Integration
### Configuration
	- `client = OpenAI(api_key=os.getenv("CLARIFAI_API_KEY"), base_url=os.getenv("CLARIFAI_BASE_URL"))`
	- Model IDs correspond to Clarifai models exposed via the compatibility layer.

### Reference Sample (Clarifai Docs)
Clarifai highlights that Gemini 2.5 Pro can be called through any client library, including OpenAI-compatible endpoints:

```python
from openai import OpenAI

client = OpenAI(
	api_key="CLARIFAI_API",  # Clarifai PAT
	base_url="https://api.clarifai.com/v2/ext/openai/v1",
)

response = client.chat.completions.create(
	model="gcp/generate/models/gemini-2_5-pro",
	messages=[
		{"role": "system", "content": "You are a helpful assistant."},
		{"role": "user", "content": "Who are you?"},
	],
	tools=None,
	tool_choice=None,
	max_completion_tokens=100,
	temperature=0.7,
	stream=True,
)
```

This mirrors the behavior surfaced in our CLI samples and UI presets.

### Model Discovery
- Attempt to list models via Clarifai’s model listing API and filter for text-generation capability.
- Fallback: Use a curated list or allow manual entry.

### Token Usage
- Prefer API `usage` fields: `prompt_tokens`, `completion_tokens`, `total_tokens` when provided.
- If absent, estimate using `tiktoken` (select encoding closest to the chosen model) or character-to-token heuristic.

### Streaming & Timing
- Start a timer before sending the request (`perf_counter`).
- TTFT: time until the first streamed chunk containing `delta.content` arrives.
- Total API Time: time until the final chunk (stream completed) or non-stream response received.
- Collect per-chunk timestamps for optional advanced diagnostics.

## Data Model
Ephemeral session state only (no persistence). Objects:
- `SessionConfig`: API key, base URL, preferred region.
- `RunParams`: model, temperature, max_completion_tokens, top_p.
- `RunResult`: text, metrics (prompt_tokens, completion_tokens, ttft_ms, total_ms), diagnostics.

## Security & Configuration
- Store secrets in Streamlit `st.secrets` or environment variables.
- Never echo the API key in UI or logs.
- Validate environment on startup; show guidance if missing.

### Environment Variables / Secrets
- `CLARIFAI_API_KEY`: required.
- `CLARIFAI_BASE_URL`: required; Clarifai OpenAI-compatible endpoint.
- `CLARIFAI_PREFERRED_REGION` (optional): for routing, if supported.

## Observability & Diagnostics
- Log structured events: `event`, `timestamp_ms`, `model`, `status_code`, `attempt`, `ttft_ms`, `total_ms`, `request_id`.
- Expose a diagnostics panel showing last run details.
- On slow responses or unexpected status codes, surface a hint to check SDK diagnostics.

## Error Scenarios
- 401/403: Invalid/expired API key → show auth error.
- 429: Rate limit → automatic backoff and user message.
- 5xx: Server issue → retry up to N attempts with backoff.
- Timeout: Cancel stream and show partial diagnostics.
- Model not found / unsupported → prompt to change model.

## Testing Strategy
- Unit: 
	- Timing utilities (TTFT measurement) with simulated streams.
	- Token estimation fallback.
- Integration:
	- Streaming path against a mock or test Clarifai endpoint.
	- Error handling (401/429/5xx) with stubbed responses.
- Manual:
	- Visual check of UI components and metrics correctness.

## Acceptance Criteria
- User can select or enter a Clarifai model and run a prompt.
- Streamed response renders progressively; TTFT and total time are shown.
- Token counts are populated from API `usage` or estimated when missing.
- Error states are clear, actionable, and do not expose secrets.
- Diagnostics panel shows status code and timing metadata.

## Deployment & Run
- Local run: `streamlit run app.py` (app implementation to follow).
- Requirements: Python 3.10+, Streamlit, OpenAI SDK 1.x, `tiktoken`, `requests`.
- Configure environment/secrets before launch.

## Risks & Mitigations
- Inconsistent token reporting across models → fallback estimation.
- Unavailable model listing → manual entry and cached lists.
- Streaming differences across providers → abstract stream handling and test.

## Future Enhancements
- Conversation history and multi-turn sessions.
- Export run results (CSV/JSON) and batch benchmarking.
- Model capability metadata and advanced filtering.
- Parallel runs for comparative timing.

