# Tasks Plan – Clarifai Token Estimator Streamlit App

## Milestones
- [x] M1: Project Scaffolding — Initialize repo files, app layout, and configuration.
- [x] M2: Clarifai Integration — OpenAI-compatible client, model listing, prompt execution.
- [x] M3: Metrics & Diagnostics — TTFT, total time, token counts, logging.
- [x] M4: Error Handling & Retries — Backoff, graceful UI errors.
- [x] M5: Testing & QA — Unit/integration tests, manual checklist.
- [x] M6: Packaging & Run — Requirements, README, quick run commands.
- [ ] M7: Optional Enhancements — Persistence/benchmarking, Cosmos DB logging.

## Milestone Checklists

### M1: Project Scaffolding
- [x] Create app.py, requirements.txt, README.md, and optional .streamlit/secrets.toml.
- [x] Build Streamlit layout with sidebar configuration and main interaction panels.
- [x] Load CLARIFAI_API_KEY and CLARIFAI_BASE_URL from st.secrets or environment variables.
- [x] Verify the app starts and renders the baseline UI.

### M2: Clarifai Integration
- [x] Configure the OpenAI SDK client with Clarifai base_url and API key.
- [x] Implement list_text_models() with text-generation filtering and manual entry fallback.
- [x] Implement streaming completion requests and optional non-stream fallback.
- [x] Expose temperature, max_completion_tokens, top_p, and penalty parameters in the UI.
- [x] Confirm prompts run against the selected model with streamed text output.

### M3: Metrics & Diagnostics
- [x] Measure TTFT using perf_counter from request start to first streamed token.
- [x] Measure total request time until the stream completes.
- [x] Capture API usage prompt_tokens and completion_tokens with tiktoken fallback.
- [x] Render a diagnostics panel with status code, request ID, attempt count, and timings.
- [x] Display response text alongside metrics cards in the UI.

### M4: Error Handling & Retries
- [x] Add exponential backoff for 429 and 5xx responses with configurable attempts.
- [x] Present user-friendly error messages without exposing secrets.
- [x] Handle streaming timeouts by cancelling and surfacing partial diagnostics.
- [x] Log structured events with error context and retry metadata.

### M5: Testing & QA
- [x] Unit test TTFT measurement helpers and token estimation fallbacks.
- [x] Integration test streaming flow and error handling with mocked responses.
- [x] Manual QA: streaming response visibility, metric accuracy, retry behaviour.
- [x] Document test coverage and residual risks.

### M6: Packaging & Run
- [x] Pin dependencies for streamlit, openai (1.x), tiktoken, and requests in requirements.txt.
- [x] Document setup, secrets configuration, and run steps in README.md.
- [x] Provide quick-start commands for virtualenv creation, installation, and streamlit run.
- [x] Ensure the app runs locally with the documented instructions.

### M7: Optional Enhancements
- [ ] Persist run history to CSV or JSON with export controls.
- [ ] Add benchmarking mode to compare TTFT and latency across models.
- [ ] Integrate Cosmos DB logging following partitioning and retry best practices.

## Cross-Cutting Checklist
- [x] Scaffold UI covering sidebar configuration and main panels.
- [x] Validate secrets loading and environment guardrails.
- [x] Configure OpenAI client with Clarifai base_url and API key.
- [x] Implement model listing with graceful fallback.
- [x] Deliver streaming execution with TTFT capture.
- [x] Support optional non-stream execution path.
- [x] Populate token metrics via API usage or tiktoken estimation.
- [x] Surface diagnostics with status codes, IDs, and timing data.
- [x] Implement exponential backoff for rate limits and server errors.
- [x] Create unit tests for timing and token utilities.
- [x] Create integration tests for streaming and error scenarios.
- [x] Finalise README with setup, run, and usage guidance.
- [x] Maintain pinned dependency versions in requirements.txt.

## Dependencies & Assumptions
- [x] Confirm availability of Python 3.10+, Streamlit, OpenAI SDK 1.x, tiktoken, and requests.
- [x] Validate Clarifai OpenAI-compatible endpoint exposes target text models and usage metrics.

## Acceptance Criteria
- [x] Model selection supports Clarifai list or manual entry and executes prompts successfully.
- [x] Streaming responses appear progressively with accurate TTFT and total time.
- [x] Token counts are populated via API usage or clearly labelled estimates.
- [x] Diagnostics surface status, request IDs, and timing with retry context.
- [x] Secrets remain hidden in logs and UI.

## Risks & Mitigations
- [x] Address token reporting variability with tiktoken fallback and labelling.
- [x] Mitigate model listing outages with manual entry and cached IDs.
- [x] Normalise streaming differences via abstraction and targeted tests.
