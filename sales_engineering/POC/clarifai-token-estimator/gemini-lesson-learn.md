# Gemini Lessons Learned

## Summary
- We now ship `GeminiGenerateClient`, a helper that drives Clarifai’s native `generate()` stream, aggregates the chunks into plain text, and estimates prompt/completion tokens via `tiktoken` plus size-based image overhead so text and multimodal prompts both surface usage-style metrics.
- GPT-4o (vision) and GPT-5.1 (text) work reliably via the OpenAI-compatible endpoint.
- Gemini 2.5 Pro still fails on the OpenAI-compatible `chat.completions` path with HTTP 500 "No completion tokens reported by the model".
- The legacy `Model.predict(image=..., prompt=...)` path continues to trigger the serializer "string_value: NoneType" error, so we now bypass it entirely via `generate()`.
- Current state: Gemini coverage runs through the new helper while production defaults remain GPT-4o/GPT-5.1 until we finish hardening.

## What We Implemented
- OpenAI-compatible image description tests and scripts
  - Local image, streaming, and remote URL tests using GPT-4o in [tests/test_integration_image_description.py](tests/test_integration_image_description.py)
  - Simple chat example defaulting to GPT-4o in [scripts/simple_chat_completion.py](scripts/simple_chat_completion.py)
  - Multimodal CLI using GPT-4o in [scripts/multimodal_input.py](scripts/multimodal_input.py)
- Gemini native generate path
  - Streaming helper in [clarifai_token_estimator/gemini_generate.py](clarifai_token_estimator/gemini_generate.py) that normalizes the `generate()` chunks, captures TTFT/latency, and now estimates prompt/completion tokens via `tiktoken` while adding a size-aware image overhead so callers get usage-style metrics even though the API omits them.
  - Updated example in [scripts/gemini-pro-example.py](scripts/gemini-pro-example.py) plus integration coverage in [tests/test_integration_image_description.py](tests/test_integration_image_description.py) using the helper.
- App defaults and configuration
  - Streamlit placeholder and model list updated to GPT-4o/GPT-5.1 in [app.py](app.py) and [.streamlit/app-settings.toml](.streamlit/app-settings.toml)
- CI/dev scripts
  - Test runner updated in [run_integration_tests.sh](run_integration_tests.sh)

## Reproduction
- Environment prerequisites
  - Set `CLARIFAI_PAT` to a valid Personal Access Token.
  - Python 3.12 with `openai` and `clarifai` SDKs installed.
- Commands
```bash
# Run all integration tests
python -m pytest tests/test_integration_image_description.py -v -s

# Focus: Gemini via native SDK generate() helper
python -m pytest tests/test_integration_image_description.py::test_gemini_pro_image_with_native_sdk -v -s

# Standalone streaming sample
python scripts/gemini-pro-example.py
```

## Observed Failures
- OpenAI-compatible endpoint (Gemini 2.5 Pro)
  - Symptom: HTTP 500
  - Details: {"code": 99009, "description": "Internal error", "details": "No completion tokens reported by the model"}
  - Path: `client.chat.completions.create()` using model URL `.../gemini-2_5-pro/...`
- Native Clarifai SDK predict() (Gemini 2.5 Pro)
  - Symptom: Exception from runner serializer
  - Details (excerpt):
    - "Incompatible type for string_value: NoneType"
    - Stack trace references `clarifai.runners.utils.serializers.serialize` called from `model_class._convert_output_to_proto`
  - Path: `Model(url=...).predict(prompt=..., image=Image(url=...))`
  - Status: We avoid this code path and instead rely on the streaming `generate()` helper described above.

## Analysis / Hypotheses
- OpenAI-compatible path
  - Gemini endpoint likely not wired to report completion tokens for this route; returns 500 despite valid input.
- Native SDK path
  - The model runner’s output does not map to the expected protobuf (a `string_value` field is `None`).
  - Indicates a mismatch between runner output and the SDK serializer contract for this model/method.
- Clarifai note: Gemini supports `generate`-style flows instead of `chat.completions`. Our native `predict()` usage aligns with the SDK example but still surfaces a runner-side serialization issue.

## Current Mitigations
- Default to GPT-4o/GPT-5.1 for production paths.
- Keep Gemini exercises isolated and marked as non-blocking in tests.
- Ensure clear logs and diagnostics for Gemini-only failures.

## Action Plan
- Engage Clarifai support with repro and request IDs
  - Provide stack traces and exact request context (model URL, prompt, image URL, parameters).
  - Ask for guidance on the correct invocation (e.g., `generate` API contract) and runner-side fix timeline.
- Validate supported interfaces for Gemini on Clarifai
  - Confirm the recommended client path (e.g., specific SDK method or REST route) and output schema.
  - Test a pure-text `generate` call (no image) to isolate the multimodal path.
- Parameter and payload hardening
  - Re-test with minimal parameters (omit `temperature`, `max_tokens`) and confirm required fields.
  - Try explicit model version vs. model alias.
- SDK/runtime alignment
  - Verify latest `clarifai` SDK and regenerate a minimal env for controlled testing.
  - Capture SDK/runner versions in logs for repeatability.
- Productization guardrails
  - Continue to forbid Gemini in default configs and UI inputs until green.
  - Keep `xfail` coverage with verbose logs and clear error reasons.

## Next Steps
- Owner: Engineering
  - Capture request IDs from the new `generate()` runs (text + multimodal) and share them with Clarifai support alongside the lingering OpenAI-compatible failure.
  - Exercise the helper with multiple prompts/images to validate stability, TTFT, and latency metrics, then wire it into the app’s adapter layer.
  - Keep documenting edge cases (tool calls, reasoning params) and expand coverage once baseline text+image runs stay green.

## Execution Plan (Proceed)
- Phase 0 — Stabilize (done): Keep GPT-4o/GPT-5.1 as defaults; gate Gemini behind tests only.
- Phase 1 — Support Ticket + MRE (Day 0):
  - Capture request IDs and stack traces from failing runs; attach to ticket.
  - Provide exact payloads and environment details; ask for supported interface (`generate`) and schema.
- Phase 2 — Validate Text `generate` (Day 0–1):
  - ✅ Helper implemented (`GeminiGenerateClient`) that aggregates the streaming `generate()` response.
  - Next: run live prompts to confirm stability, capture TTFT/usage, and compare against success criteria (non-empty text, no serialization errors, consistent metrics).
- Phase 3 — Validate Multimodal (Day 1–2):
  - Extend helper invocations to cover URL + data URL inputs, different formats, and verify model limits.
  - Success criteria: coherent description, stable latency, no runner serialization errors.
- Phase 4 — Adapter + Tests (Day 2):
  - Create a `GeminiAdapter` that routes calls to the supported interface while matching our app contract.
  - Replace `xfail` with green tests; add regression tests for text and image flows.
- Phase 5 — Rollout (Day 3):
  - Unhide Gemini in UI configs; keep a feature flag for quick rollback.
  - Monitor logs; document known limits and examples.

Ownership
- DRI: Engineering (SDK integration), with Support liaison for ticketing.
- Reviewers: App owners for UI/flag changes; QA for regression coverage.

Acceptance Criteria
- Text and multimodal Gemini calls succeed without serialization errors.
- Tests pass reliably in CI with diagnostics enabled.
- UI can toggle Gemini safely via config/flag.

## Appendix
- Key files
  - Tests: [tests/test_integration_image_description.py](tests/test_integration_image_description.py)
  - Example script: [scripts/gemini-pro-example.py](scripts/gemini-pro-example.py)
  - Gemini helper: [clarifai_token_estimator/gemini_generate.py](clarifai_token_estimator/gemini_generate.py)
  - Multimodal CLI: [scripts/multimodal_input.py](scripts/multimodal_input.py)
  - App: [app.py](app.py), [.streamlit/app-settings.toml](.streamlit/app-settings.toml)
  - Runner: [run_integration_tests.sh](run_integration_tests.sh)
- Sample error strings
  - OpenAI-compatible: "No completion tokens reported by the model"
  - Native SDK: "Incompatible type for string_value: NoneType"
