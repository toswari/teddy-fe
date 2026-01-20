"""Streamlit application for Clarifai OpenAI-compatible token estimator."""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from clarifai_token_estimator.clarifai_client import ClarifaiOpenAIClient, GenerationParams
from clarifai_token_estimator.gemini_generate import (
    DEFAULT_GEMINI_MODEL_URL,
    GeminiGenerateClient,
)
from clarifai_token_estimator.metrics import InferenceMetrics, build_metrics

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

PAGE_TITLE = "Clarifai Token Estimator"
DEFAULT_BASE_URL = "https://api.clarifai.com/v2/ext/openai/v1"
PROJECT_ROOT = Path(__file__).resolve().parent
APP_CONFIG_PATH = PROJECT_ROOT / ".streamlit" / "app-settings.toml"
INFERENCE_MODE_OPTIONS = {
    "openai": "OpenAI-compatible (chat.completions)",
    "gemini": "Gemini native generate()",
}
MAX_DEBUG_SNIPPET = 400


def _load_app_config() -> Dict[str, Any]:
    if not APP_CONFIG_PATH.exists():
        return {}
    try:
        with APP_CONFIG_PATH.open("rb") as fh:
            parsed = tomllib.load(fh)
    except Exception:  # noqa: BLE001
        return {}
    app_config = parsed.get("app", {}) or {}
    if not isinstance(app_config, dict):
        return {}
    return app_config


APP_CONFIG = _load_app_config()

PROMPT_PRESETS = {
    "Custom": {},
    "Product Photo Inspection": {
        "system": APP_CONFIG.get("default_system_prompt", ""),
        "prompt": APP_CONFIG.get("default_prompt", ""),
        "image_url": APP_CONFIG.get("default_image_url", ""),
    },
    "Simple Chat Greeting": {
        "system": "You are a helpful assistant.",
        "prompt": "Who are you?",
    },
}


def _compose_prompt(system_prompt: str, user_prompt: str) -> str:
    system_clean = (system_prompt or "").strip()
    user_clean = (user_prompt or "").strip()
    if system_clean and user_clean:
        return f"{system_clean}\n\n{user_clean}"
    if system_clean:
        return system_clean
    return user_clean


def _get_secret(name: str, *, fallback: Optional[str] = None) -> str:
    try:
        return st.secrets[name]
    except Exception:  # noqa: BLE001
        env_key = name.upper()
        env_value = os.getenv(env_key)
        if env_value:
            return env_value
        return fallback or ""


def _initialize_session_state() -> None:
    st.session_state.setdefault("clarifai", {})
    config = st.session_state["clarifai"]
    if "api_key" not in config:
        config["api_key"] = _get_secret("CLARIFAI_PAT")
    if "base_url" not in config:
        config["base_url"] = _get_secret("CLARIFAI_BASE_URL", fallback=DEFAULT_BASE_URL)
    if "preferred_region" not in config:
        config["preferred_region"] = _get_secret("CLARIFAI_PREFERRED_REGION")
    st.session_state.setdefault("latest_result", None)
    st.session_state.setdefault("prompt_value", APP_CONFIG.get("default_prompt", ""))
    st.session_state.setdefault("system_prompt_value", APP_CONFIG.get("default_system_prompt", ""))
    st.session_state.setdefault("image_url_value", APP_CONFIG.get("default_image_url", ""))
    st.session_state.setdefault("prompt_preset", "Custom")
    configured_models = APP_CONFIG.get("model_urls", []) or []
    if configured_models:
        st.session_state.setdefault("configured_model", configured_models[0])
    else:
        st.session_state.setdefault("configured_model", "")


def _apply_prompt_preset() -> None:
    selection = st.session_state.get("prompt_preset", "Custom")
    preset = PROMPT_PRESETS.get(selection)
    if not preset:
        return
    st.session_state["system_prompt_value"] = preset.get("system", "")
    st.session_state["prompt_value"] = preset.get("prompt", "")
    if "image_url" in preset:
        st.session_state["image_url_value"] = preset.get("image_url", "")


def _sidebar_configuration() -> Dict[str, str]:
    config = st.session_state["clarifai"]
    st.sidebar.header("Configuration")
    api_key = st.sidebar.text_input(
        "Clarifai PAT",
        value=config.get("api_key", ""),
        type="password",
        help="Personal Access Token for Clarifai authentication.",
    )
    base_url = st.sidebar.text_input(
        "Clarifai Base URL",
        value=config.get("base_url", DEFAULT_BASE_URL),
        help="Provide the OpenAI-compatible base URL for Clarifai (e.g. https://api.clarifai.com/v1).",
    )
    preferred_region = st.sidebar.text_input(
        "Preferred Region (optional)",
        value=config.get("preferred_region", ""),
        help="Clarifai region routing hint if supported.",
    )
    config.update({"api_key": api_key.strip(), "base_url": base_url.strip(), "preferred_region": preferred_region.strip()})
    return config


def _render_metrics(metrics: InferenceMetrics) -> None:
    prompt_label = metrics.prompt_tokens if metrics.prompt_tokens is not None else "—"
    completion_label = metrics.completion_tokens if metrics.completion_tokens is not None else "—"
    ttft_label = f"{metrics.ttft_ms:.0f} ms" if metrics.ttft_ms is not None else "—"
    total_label = f"{metrics.total_time_ms:.0f} ms" if metrics.total_time_ms is not None else "—"

    col_prompt, col_completion, col_ttft, col_total = st.columns(4)
    col_prompt.metric("Input Tokens", prompt_label)
    col_completion.metric("Output Tokens", completion_label)
    col_ttft.metric("Time To First Token", ttft_label)
    col_total.metric("Total API Time", total_label)

    if metrics.estimated:
        st.caption("Token counts estimated locally; Clarifai did not return usage in the response.")


def _render_diagnostics(diagnostics: Dict[str, str]) -> None:
    with st.expander("Diagnostics"):
        st.json(diagnostics)


def _render_debug(debug: Dict[str, Any]) -> None:
    with st.expander("Debug (Request & Response)"):
        col_req, col_res = st.columns(2)
        with col_req:
            st.subheader("Request")
            st.json(debug.get("request", {}))
        with col_res:
            st.subheader("Response")
            st.json(debug.get("response", {}))


def _build_generation_params() -> GenerationParams:
    st.sidebar.subheader("Generation Parameters")
    temperature = st.sidebar.slider("Temperature", min_value=0.0, max_value=2.0, value=0.7, step=0.1)
    max_completion_tokens_toggle = st.sidebar.checkbox("Set Max Completion Tokens", value=False)
    max_completion_tokens = (
        st.sidebar.number_input("Max Completion Tokens", min_value=1, max_value=8192, value=512, step=16)
        if max_completion_tokens_toggle
        else None
    )
    top_p = st.sidebar.slider("Top-p", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
    presence_penalty = st.sidebar.slider("Presence Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    frequency_penalty = st.sidebar.slider("Frequency Penalty", min_value=-2.0, max_value=2.0, value=0.0, step=0.1)
    stream = st.sidebar.checkbox("Stream Responses", value=False)

    return GenerationParams(
        temperature=temperature,
        max_completion_tokens=int(max_completion_tokens) if max_completion_tokens is not None else None,
        top_p=top_p,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        stream=stream,
    )


def _prepare_image_payload(uploaded_file: Optional[Any]) -> tuple[Optional[str], Optional[bytes], Optional[str]]:
    """Return (data_url, raw_bytes, mime_type) for an uploaded image."""

    if not uploaded_file:
        return None, None, None
    image_bytes = uploaded_file.getvalue()
    if not image_bytes:
        return None, None, None
    mime_type = uploaded_file.type or mimetypes.guess_type(getattr(uploaded_file, "name", ""))[0] or "image/png"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    return data_url, image_bytes, mime_type


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    st.title(PAGE_TITLE)
    st.write("Interact with Clarifai's OpenAI-compatible models, streaming responses while tracking tokens and latency.")

    _initialize_session_state()
    config = _sidebar_configuration()
    params = _build_generation_params()

    st.selectbox(
        "Prompt Preset",
        options=list(PROMPT_PRESETS.keys()),
        key="prompt_preset",
        on_change=_apply_prompt_preset,
        help="Quickly load sample system/prompt combos (custom preserves your edits).",
    )

    system_prompt = st.text_area(
        "System Message (optional)",
        key="system_prompt_value",
        placeholder="You are a helpful assistant that inspects product photos.",
        height=140,
    )

    prompt = st.text_area(
        "Prompt",
        key="prompt_value",
        placeholder="Write a Clarifai-compatible prompt...",
        height=220,
    )

    inference_mode_label = st.radio(
        "Inference Pathway",
        options=list(INFERENCE_MODE_OPTIONS.values()),
        help=(
            "Use the OpenAI-compatible route for GPT-4o/GPT-5.1 models, or switch to the "
            "Gemini native generate() flow to call Clarifai's Gemini 2.5 Pro deployment."
        ),
    )
    use_gemini_mode = inference_mode_label == INFERENCE_MODE_OPTIONS["gemini"]
    if use_gemini_mode:
        st.success(
            "Gemini 2.5 Pro mode enabled – calls Clarifai's native generate() API with the "
            "same PAT and provides token estimates (including image size overhead)."
        )
    else:
        st.caption(
            "OpenAI-compatible mode streams GPT-4o/GPT-5.1 responses via Clarifai's /ext/openai endpoint."
        )

    api_key = config["api_key"]
    base_url = config["base_url"]

    client: Optional[ClarifaiOpenAIClient] = None
    if not use_gemini_mode:
        if api_key and base_url:
            try:
                client = ClarifaiOpenAIClient(api_key=api_key, base_url=base_url)
            except ValueError as config_error:
                st.error(str(config_error))
                return
            except RuntimeError as runtime_error:
                st.error(str(runtime_error))
                return
        else:
            st.info("Provide Clarifai credentials in the sidebar to enable inference.")
            client = None
    else:
        if not api_key:
            st.info("Provide a Clarifai PAT in the sidebar to enable Gemini inference.")

    configured_models: List[str] = APP_CONFIG.get("model_urls", []) or []
    preset_model = st.session_state.get("configured_model", "")
    if use_gemini_mode:
        if DEFAULT_GEMINI_MODEL_URL not in configured_models:
            configured_models = [DEFAULT_GEMINI_MODEL_URL] + configured_models
        if preset_model not in configured_models:
            st.session_state["configured_model"] = DEFAULT_GEMINI_MODEL_URL
    else:
        if preset_model and preset_model not in configured_models and configured_models:
            st.session_state["configured_model"] = configured_models[0]
    selected_model = ""
    if configured_models:
        st.selectbox(
            "Configured Model URLs",
            options=configured_models,
            key="configured_model",
            help="Loaded from .streamlit/app-settings.toml",
        )
        selected_model = st.session_state.get("configured_model", "")

    manual_model = st.text_input(
        "Model URL override",
        value="",
        placeholder="openai/chat-completion/models/gpt-4o",
        help="Paste a Clarifai model URL to override the configured options.",
    ).strip()

    model_id = manual_model or selected_model
    if use_gemini_mode and not model_id:
        model_id = DEFAULT_GEMINI_MODEL_URL

    uploaded_image = st.file_uploader(
        "Optional image attachment",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        help="Attach an image to send alongside the prompt for multimodal inference.",
    )
    image_data_url, image_preview_bytes, image_mime = _prepare_image_payload(uploaded_image)

    image_url_input = st.text_input(
        "Image URL (optional)",
        key="image_url_value",
        placeholder="https://example.com/path/to/image.jpg",
        help="Provide a remote image URL to send instead of uploading a file.",
    ).strip()
    image_remote_url: Optional[str] = image_url_input or None
    preview_items: List[tuple[Any, str]] = []
    if image_preview_bytes:
        preview_items.append((image_preview_bytes, f"Uploaded image ({image_mime})"))
    if image_url_input:
        image_data_url = image_url_input
        preview_items.append((image_url_input, "Remote image (URL)"))

    if preview_items:
        with st.expander("Image Preview", expanded=False):
            for data, caption in preview_items:
                st.image(data, caption=caption, width=600)

    run_button = st.button("Run Inference", type="primary")

    output_placeholder = st.empty()

    def _render_response_area(text: str, *, use_new_key: bool = True) -> None:
        counter_key = "response_display_nonce"
        if use_new_key or counter_key not in st.session_state:
            st.session_state[counter_key] = st.session_state.get(counter_key, -1) + 1
        key_suffix = st.session_state[counter_key]
        output_placeholder.empty()
        output_placeholder.text_area(
            "Response",
            value=text,
            height=260,
            placeholder="Model output will appear here...",
            key=f"response_display_{key_suffix}",
            disabled=True,
        )

    initial_response_text = ""
    if st.session_state.get("latest_result"):
        initial_response_text = st.session_state["latest_result"].get("text", "")
    _render_response_area(initial_response_text)

    if run_button:
        if not api_key:
            st.error("Clarifai PAT is required to run inference.")
            return
        if not model_id:
            st.error("Select or enter a Clarifai model ID before running.")
            return
        if not prompt.strip():
            st.error("Enter a prompt to run the inference.")
            return
        if not use_gemini_mode and not client:
            st.error("Clarifai configuration is incomplete.")
            return

        fragments: List[str] = []
        _render_response_area("", use_new_key=True)

        def _on_chunk(text_delta: str) -> None:
            fragments.append(text_delta)
            _render_response_area("".join(fragments), use_new_key=True)

        system_prompt_clean = system_prompt.strip()
        combined_prompt = _compose_prompt(system_prompt_clean, prompt)

        gemini_result = None
        openai_result = None
        try:
            with st.spinner("Calling Clarifai..."):
                if use_gemini_mode:
                    gemini_client = GeminiGenerateClient(
                        pat=api_key,
                        model_url=model_id or DEFAULT_GEMINI_MODEL_URL,
                    )
                    gemini_kwargs: Dict[str, Any] = {
                        "prompt": combined_prompt,
                        "temperature": params.temperature,
                        "top_p": params.top_p,
                        "estimate_tokens": True,
                    }
                    if params.max_completion_tokens is not None:
                        gemini_kwargs["max_tokens"] = params.max_completion_tokens
                    if image_preview_bytes:
                        gemini_kwargs["image_bytes"] = image_preview_bytes
                    elif image_remote_url:
                        gemini_kwargs["image_url"] = image_remote_url
                    gemini_result = gemini_client.generate(**gemini_kwargs)
                else:
                    openai_result = client.stream_chat_completion(
                        model=model_id,
                        prompt=prompt,
                        params=params,
                        on_text_chunk=_on_chunk,
                        image_data=image_data_url,
                        system_prompt=system_prompt_clean or None,
                    )
        except Exception as error:  # noqa: BLE001
            st.error(f"Clarifai request failed: {error}")
            return

        if use_gemini_mode and gemini_result is not None:
            response_text = gemini_result.text or ""
            _render_response_area(response_text, use_new_key=True)
            image_bytes_len = len(image_preview_bytes) if image_preview_bytes else None
            result_payload = {
                "text": response_text,
                "usage": gemini_result.usage,
                "ttft_ms": gemini_result.ttft_ms,
                "total_time_ms": gemini_result.total_time_ms,
                "diagnostics": {
                    "mode": "gemini.generate",
                    "model_url": gemini_result.model_url,
                    "chunk_count": gemini_result.chunk_count,
                    "image_tokens": gemini_result.image_tokens,
                },
                "debug": {
                    "request": {
                        "prompt": combined_prompt[:MAX_DEBUG_SNIPPET],
                        "image_source": "upload" if image_preview_bytes else ("url" if image_remote_url else None),
                        "image_bytes": image_bytes_len,
                        "image_url": None if image_preview_bytes else image_remote_url,
                        "temperature": params.temperature,
                        "top_p": params.top_p,
                        "max_tokens": params.max_completion_tokens,
                    },
                    "response": {
                        "text": response_text[:MAX_DEBUG_SNIPPET],
                        "usage": gemini_result.usage,
                        "chunk_count": gemini_result.chunk_count,
                        "ttft_ms": gemini_result.ttft_ms,
                        "total_time_ms": gemini_result.total_time_ms,
                        "image_tokens": gemini_result.image_tokens,
                    },
                },
            }
        elif openai_result is not None:
            response_text = openai_result.text or ""
            if not fragments:
                _render_response_area(response_text, use_new_key=True)
            result_payload = {
                "text": response_text,
                "usage": openai_result.usage,
                "ttft_ms": openai_result.ttft_ms,
                "total_time_ms": openai_result.total_time_ms,
                "diagnostics": openai_result.diagnostics,
                "debug": openai_result.debug,
            }
        else:
            st.error("Unexpected state: inference completed without a result.")
            return

        metrics = build_metrics(
            result_payload.get("usage"),
            combined_prompt,
            response_text,
            model_id,
            result_payload.get("ttft_ms"),
            result_payload.get("total_time_ms"),
        )
        st.session_state["latest_result"] = {
            "text": response_text,
            "metrics": metrics,
            "diagnostics": result_payload.get("diagnostics", {}),
            "debug": result_payload.get("debug", {}),
        }
        _render_metrics(metrics)
        _render_diagnostics(result_payload.get("diagnostics", {}))
        _render_debug(result_payload.get("debug", {}))

    if st.session_state.get("latest_result") and not run_button:
        last = st.session_state["latest_result"]
        _render_metrics(last["metrics"])
        _render_diagnostics(last["diagnostics"])
        _render_debug(last.get("debug", {}))


if __name__ == "__main__":
    main()
