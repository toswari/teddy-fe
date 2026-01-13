"""Helpers for interacting with local LM Studio VLM endpoints."""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import cv2
import numpy as np
import requests
from openai import BadRequestError, OpenAI
from sqlalchemy import delete
from flask import current_app


def _reports_root() -> Path:
    try:
        base = current_app.config.get("REPORTS_ROOT")
        if base:
            return Path(base)
    except RuntimeError:
        pass
    return Path("reports")

from app.extensions import db
from app.models import Detection, InferenceRun
from app.services.reporting_service import draw_frame_overlay

LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an assistant that detects brand logos in images. "
    "Return only JSON, with fields: detections[], each with label, confidence (0-1), "
    "bbox {left, top, right, bottom} normalized to [0,1]. No extra text."
)

USER_PROMPT_TEMPLATE = (
    "Analyze the image and identify logos. "
    "Return JSON only in this schema: \n"
    "{\n  \"detections\": [\n    {\n      \"label\": \"...\",\n      \"confidence\": 0.95,\n      \"bbox\": {\"left\": 0.12, \"top\": 0.22, \"right\": 0.35, \"bottom\": 0.48}\n    }\n  ]\n}\n"
)

# Recommended models we always surface to keep the UI populated.
PINNED_VLM_MODELS: List[Dict[str, Any]] = [
    {
        "id": "qwen/qwen2.5-vl-7b",
        "name": "Qwen2.5-VL 7B",
        "description": "Qwen vision-language 7B baseline for logo detection.",
        "pinned": True,
    },
    {
        "id": "zai-org/glm-4.6v-flash",
        "name": "GLM 4.6v Flash",
        "description": "Fast GLM multi-modal model for comparison runs.",
        "pinned": True,
    },
]

PINNED_VLM_IDS: Set[str] = {model["id"] for model in PINNED_VLM_MODELS}


class VLMServiceError(RuntimeError):
    """Raised when LM Studio interactions fail."""


def _merge_pinned_models(remote: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure pinned VLM entries are present and consistently labeled."""

    seen: Dict[str, Dict[str, Any]] = {}
    for entry in remote:
        model_id_raw = entry.get("id")
        if not model_id_raw:
            continue
        model_id = str(model_id_raw)
        merged = dict(entry)
        merged["id"] = model_id
        merged["name"] = merged.get("name") or model_id
        merged["pinned"] = bool(merged.get("pinned") or model_id in PINNED_VLM_IDS)
        seen[model_id] = merged

    ordered: List[Dict[str, Any]] = []
    for pinned in PINNED_VLM_MODELS:
        model_id = pinned["id"]
        existing = seen.pop(model_id, None)
        if existing:
            existing["name"] = pinned.get("name") or existing.get("name") or model_id
            if pinned.get("description") and not existing.get("description"):
                existing["description"] = pinned["description"]
            existing["pinned"] = True
            ordered.append(existing)
        else:
            fallback = dict(pinned)
            ordered.append(fallback)

    remaining = sorted(
        seen.values(),
        key=lambda item: (item.get("name") or item["id"]),
    )
    ordered.extend(remaining)
    return ordered


def _build_models_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise VLMServiceError("LM Studio base URL is not configured.")
    if base.endswith("/models"):
        return base
    return f"{base}/models"


def list_models(base_url: str, api_key: Optional[str] = None, timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Fetch available models from LM Studio's /models endpoint."""

    url = _build_models_url(base_url)
    headers: Dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise VLMServiceError(f"Unable to reach LM Studio at {url}: {exc}") from exc

    if response.status_code != 200:
        snippet = response.text.strip() or response.reason or "Unknown error"
        snippet = snippet[:200]
        raise VLMServiceError(f"LM Studio responded with {response.status_code}: {snippet}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VLMServiceError("LM Studio returned invalid JSON.") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise VLMServiceError("Unexpected LM Studio response shape.")

    models: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("name")
        if not model_id:
            continue
        models.append(
            {
                "id": model_id,
                "name": item.get("name") or model_id,
                "description": item.get("description"),
                "owned_by": item.get("owned_by"),
            }
        )

    return _merge_pinned_models(models)


def extract_json_only(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        closing = text.rfind("```")
        if closing > 0:
            inner = text[3:closing].strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            text = inner
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return text
    candidate = text[first : last + 1]
    cursor = last
    while cursor > first:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            cursor = text.rfind("}", first, cursor)
            if cursor <= first:
                break
            candidate = text[first : cursor + 1]
    return text


def _normalize_bbox(values: List[float], width: Optional[int], height: Optional[int]) -> List[float]:
    if width and height and any(v > 1.0 for v in values):
        x1 = max(0.0, min(1.0, values[0] / float(width)))
        y1 = max(0.0, min(1.0, values[1] / float(height)))
        x2 = max(0.0, min(1.0, values[2] / float(width)))
        y2 = max(0.0, min(1.0, values[3] / float(height)))
        return [x1, y1, x2, y2]
    return values


def _coerce_detections(payload: Dict[str, Any], width: Optional[int], height: Optional[int]) -> List[Dict[str, Any]]:
    detections: List[Dict[str, Any]] = []
    for det in (payload.get("detections") or []):
        label = det.get("label")
        bbox = det.get("bbox")
        if not label or bbox is None:
            continue

        values: Optional[List[float]] = None
        if isinstance(bbox, dict):
            keys_ltrb = [bbox.get("left"), bbox.get("top"), bbox.get("right"), bbox.get("bottom")]
            keys_xyxy = [bbox.get("x1"), bbox.get("y1"), bbox.get("x2"), bbox.get("y2")]
            try:
                if all(v is not None for v in keys_ltrb):
                    values = [float(keys_ltrb[0]), float(keys_ltrb[1]), float(keys_ltrb[2]), float(keys_ltrb[3])]
                elif all(v is not None for v in keys_xyxy):
                    values = [float(keys_xyxy[0]), float(keys_xyxy[1]), float(keys_xyxy[2]), float(keys_xyxy[3])]
            except (TypeError, ValueError):
                values = None
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                values = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
            except (TypeError, ValueError):
                values = None

        if values is None:
            continue

        normalized = _normalize_bbox(values, width, height)
        if any(v < 0 or v > 1 for v in normalized):
            continue

        detections.append(
            {
                "label": str(label),
                "confidence": float(det.get("confidence")) if det.get("confidence") is not None else 0.0,
                "bbox": {
                    "left": normalized[0],
                    "top": normalized[1],
                    "right": normalized[2],
                    "bottom": normalized[3],
                },
            }
        )
    return detections


def _regex_parse_detections(text: str, width: Optional[int], height: Optional[int]) -> List[Dict[str, Any]]:
    detections: List[Dict[str, Any]] = []
    for block in re.finditer(r"\{[^}]*label[^}]*\}", text, flags=re.IGNORECASE | re.DOTALL):
        snippet = block.group(0)
        m_label = re.search(r'"label"\s*:\s*"([^"]+)"', snippet)
        if not m_label:
            continue
        label = m_label.group(1)
        m_conf = re.search(r'"confidence"\s*:\s*([0-9]*\.?[0-9]+)', snippet)
        conf = float(m_conf.group(1)) if m_conf else 0.0
        m_bbox = re.search(r'"bbox"\s*:\s*\{([^}]*)\}', snippet)
        nums = None
        if m_bbox:
            nums = re.findall(r'-?\d+\.?\d*', m_bbox.group(1))
        else:
            m_list = re.search(r'"bbox"\s*:\s*\[([^\]]*)\]', snippet)
            if m_list:
                nums = re.findall(r'-?\d+\.?\d*', m_list.group(1))
        if not nums or len(nums) < 4:
            continue
        try:
            values = [float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])]
        except ValueError:
            continue
        normalized = _normalize_bbox(values, width, height)
        if any(v < 0 or v > 1 for v in normalized):
            continue
        detections.append(
            {
                "label": label,
                "confidence": conf,
                "bbox": {
                    "left": normalized[0],
                    "top": normalized[1],
                    "right": normalized[2],
                    "bottom": normalized[3],
                },
            }
        )
    return detections


def _parse_json_detections(text: str, width: Optional[int], height: Optional[int]) -> List[Dict[str, Any]]:
    data_text = extract_json_only(text)
    try:
        payload = json.loads(data_text)
    except json.JSONDecodeError:
        return _regex_parse_detections(text, width, height)
    detections = _coerce_detections(payload if isinstance(payload, dict) else {}, width, height)
    return detections or _regex_parse_detections(text, width, height)


def _load_image_bytes(image_path: Path) -> tuple[bytes, Optional[int], Optional[int], str]:
    with image_path.open("rb") as handle:
        img_bytes = handle.read()
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    try:
        img = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        height, width = (img.shape[0], img.shape[1]) if img is not None else (None, None)
    except Exception:  # noqa: BLE001
        width, height = None, None
    return img_bytes, width, height, mime


def _ensure_image_path(project_root: Path, image_path: Path) -> Path:
    if image_path.exists():
        return image_path
    candidate = project_root / image_path
    if candidate.exists():
        return candidate
    raise VLMServiceError(f"Frame image not found: {image_path}")


def _create_client(base_url: str, api_key: Optional[str]) -> OpenAI:
    if not base_url:
        raise VLMServiceError("LM Studio base URL is required")
    key = api_key or "lm-studio"
    return OpenAI(base_url=base_url, api_key=key)


def _run_vlm_on_frame(client: OpenAI, model_id: str, image_path: Path) -> tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
    img_bytes, width, height, mime = _load_image_bytes(image_path)
    data_url = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
    image_part = {"type": "image_url", "image_url": {"url": data_url}}
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": USER_PROMPT_TEMPLATE},
                image_part,
            ],
        },
    ]
    try:
        response = client.chat.completions.create(model=model_id, messages=messages, temperature=0)
    except BadRequestError as exc:
        message = str(exc)
        if "image_url" in message and ("string" in message or "must be a string" in message):
            retry_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT_TEMPLATE},
                        {"type": "image_url", "image_url": data_url},
                    ],
                },
            ]
            response = client.chat.completions.create(model=model_id, messages=retry_messages, temperature=0)
        else:
            raise VLMServiceError(f"VLM completion failed: {exc}") from exc

    content = (response.choices[0].message.content or "").strip()
    LOGGER.debug("VLM raw content (model=%s): %s", getattr(response, "model", model_id), content[:300])
    detections = _parse_json_detections(content, width, height)
    return detections, width, height


def run_vlm_for_run(
    run_id: int,
    model_id: str,
    limit: Optional[int],
    *,
    base_url: str,
    api_key: Optional[str],
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    if not model_id:
        raise VLMServiceError("modelId is required")

    inference_run = db.session.get(InferenceRun, run_id)
    if inference_run is None:
        raise VLMServiceError(f"Inference run {run_id} not found")
    frames = (inference_run.results or {}).get("frames") or []
    if not frames:
        raise VLMServiceError(f"Inference run {run_id} has no frame metadata")

    out_root = _reports_root() / f"run_{run_id}"
    json_dir = out_root / "json"
    frames_dir = out_root / "frames"
    json_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    client = _create_client(base_url, api_key)
    project_root = project_root or Path(__file__).resolve().parents[2]

    # Remove any prior detections created for this model to avoid duplicates
    db.session.execute(
        delete(Detection).where(
            Detection.inference_run_id == inference_run.id,
            Detection.model_id == model_id,
        )
    )

    processed_frames: List[Dict[str, Any]] = []
    count_limit = max(limit or 0, 0) or None
    processed = 0

    for frame in frames:
        if count_limit is not None and processed >= count_limit:
            break

        raw_index = frame.get("index")
        frame_index = int(raw_index) if raw_index is not None else processed
        timestamp_seconds = float(frame.get("timestamp_seconds") or 0.0)
        image_path = Path(frame.get("image_path") or "")

        try:
            resolved_image = _ensure_image_path(project_root, image_path)
        except VLMServiceError as exc:
            LOGGER.warning("Skipping frame %s: %s", frame_index, exc)
            continue

        detections, frame_width, frame_height = _run_vlm_on_frame(client, model_id, resolved_image)
        if frame_width is None or frame_height is None:
            fallback_image = cv2.imread(str(resolved_image))
            if fallback_image is not None:
                frame_height, frame_width = fallback_image.shape[:2]

        normalized_detections = _coerce_detections({"detections": detections}, frame_width, frame_height)
        if not normalized_detections and detections:
            normalized_detections = detections
        detections = normalized_detections
        overlay_detections = [
            {
                "label": det["label"],
                "confidence": det.get("confidence", 0.0),
                "bbox": det["bbox"],
                "model_id": "B",
            }
            for det in detections
        ]

        overlay_out = frames_dir / f"frame_{frame_index:06}_overlay.png"
        json_out = json_dir / f"model_B_frame_{frame_index:06}.json"

        with json_out.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "runId": inference_run.id,
                    "frameId": frame_index,
                    "model": model_id,
                    "detections": detections,
                },
                handle,
                indent=2,
            )

        try:
            draw_frame_overlay(resolved_image, overlay_detections, overlay_out)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Overlay failed for frame %s: %s", frame_index, exc)

        for det in detections:
            confidence = float(det.get("confidence", 0.0))
            db.session.add(
                Detection(
                    inference_run_id=inference_run.id,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                    model_id=model_id,
                    label=det.get("label"),
                    confidence=round(confidence, 4),
                    bbox=det.get("bbox", {}),
                    frame_image_path=str(resolved_image),
                )
            )

        processed_frames.append(
            {
                "frameIndex": frame_index,
                "detections": len(detections),
                "jsonPath": str(json_out),
                "overlayPath": str(overlay_out),
            }
        )
        processed += 1

    if model_id not in (inference_run.model_ids or []):
        updated_models = list(inference_run.model_ids or [])
        updated_models.append(model_id)
        inference_run.model_ids = updated_models

    # Persist overlay metadata so the UI can reuse rendered assets later.
    existing_results: Dict[str, Any] = dict(inference_run.results or {})
    overlays_meta = existing_results.get("vlm_overlays") or {}
    frames_meta = overlays_meta.get("frames") or {}
    for frame_info in processed_frames:
        frame_idx = frame_info.get("frameIndex")
        if frame_idx is None:
            continue
        frames_meta[str(frame_idx)] = {
            "overlay_path": frame_info.get("overlayPath"),
            "json_path": frame_info.get("jsonPath"),
        }
    overlays_meta["model_id"] = model_id
    overlays_meta["frames"] = frames_meta
    existing_results["vlm_overlays"] = overlays_meta
    inference_run.results = existing_results

    db.session.commit()

    return {
        "runId": inference_run.id,
        "modelId": model_id,
        "processed": processed,
        "frames": processed_frames,
        "outputsDir": str(out_root),
    }
