#!/usr/bin/env python3
"""
Simple VLM test app: run logo detection via LM Studio (OpenAI-compatible API)
against frames from an existing inference run.

Usage:
  python3 scripts/test-vlm-app.py --run-id 43 [--model-id Qwen2_5-VL-7B-Instruct] [--limit 3]

Environment:
  LMSTUDIO_BASE_URL (default: http://localhost:1234/v1)
  LMSTUDIO_MODEL_ID (overrides --model-id)

Outputs:
  - JSON per frame: reports/run_<id>/json/model_B_frame_<frame>.json
  - Overlay PNGs:   reports/run_<id>/frames/frame_<frame>_overlay.png

This script treats the VLM as "Model B" for overlay coloring (dark blue).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any
import mimetypes
import re
import numpy as np
import cv2
import logging

from openai import OpenAI, BadRequestError

# Ensure local imports work when running from project root or scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reduce noisy debug logs from HTTP and OpenAI client
for _name in ["httpx", "httpcore", "httpcore.http11", "httpcore.connection", "openai", "openai._base_client"]:
    try:
        logging.getLogger(_name).setLevel(logging.WARNING)
    except Exception:
        pass

from app import create_app  # type: ignore
from app.extensions import db  # type: ignore
from app.models import InferenceRun  # type: ignore
from app.services.reporting_service import draw_frame_overlay  # type: ignore

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

def _truncate(s: str, max_chars: int = 1000) -> str:
    try:
        return s[:max_chars] + ("…" if len(s) > max_chars else "")
    except Exception:
        return s


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run VLM inference on frames from an existing run.")
    p.add_argument("--run-id", type=int, required=False, help="Target inference run ID")
    p.add_argument("--model-id", type=str, default=os.getenv("LMSTUDIO_MODEL_ID", "florence-2-large-ft"))
    p.add_argument("--base-url", type=str, default=os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"))
    p.add_argument("--limit", type=int, default=3, help="Max frames to process (default 3)")
    p.add_argument(
        "--max-side",
        type=int,
        default=int(os.getenv("VLM_MAX_SIDE", "0")),
        help="Optional max dimension (pixels) to downscale frames before sending to the VLM",
    )
    p.add_argument("--list-models", action="store_true", help="List available local models and exit")
    return p.parse_args()


def extract_json_only(text: str) -> str:
    text = text.strip()
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


def _normalize_bbox(values: list[float], width: int | None, height: int | None) -> list[float]:
    # values: [x1, y1, x2, y2]
    if width and height and any(v > 1.0 for v in values):
        x1 = max(0.0, min(1.0, values[0] / float(width)))
        y1 = max(0.0, min(1.0, values[1] / float(height)))
        x2 = max(0.0, min(1.0, values[2] / float(width)))
        y2 = max(0.0, min(1.0, values[3] / float(height)))
        return [x1, y1, x2, y2]
    # assume already normalized
    return values


def coerce_detections(payload: dict[str, Any], width: int | None = None, height: int | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for det in (payload.get("detections") or []):
        label = det.get("label")
        bbox = det.get("bbox")
        if not label or bbox is None:
            continue

        values: list[float] | None = None
        if isinstance(bbox, dict):
            # Support either left/top/right/bottom or x1/y1/x2/y2
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

        values = _normalize_bbox(values, width, height)
        if any(v < 0 or v > 1 for v in values):
            # reject if still out of bounds and we couldn't normalize
            continue

        out.append({
            "label": str(label),
            "confidence": float(det.get("confidence")) if det.get("confidence") is not None else 0.0,
            "bbox": {"left": values[0], "top": values[1], "right": values[2], "bottom": values[3]},
        })
    return out


def parse_detections_from_text(text: str, width: int | None = None, height: int | None = None) -> list[dict[str, Any]]:
    # Fallback parser for loosely formatted outputs
    detections: list[dict[str, Any]] = []
    # Split on blocks starting with label
    for block in re.finditer(r"\{[^}]*label[^}]*\}", text, flags=re.IGNORECASE | re.DOTALL):
        btxt = block.group(0)
        m_label = re.search(r'"label"\s*:\s*"([^"]+)"', btxt)
        if not m_label:
            continue
        label = m_label.group(1)

        m_conf = re.search(r'"confidence"\s*:\s*([0-9]*\.?[0-9]+)', btxt)
        conf = float(m_conf.group(1)) if m_conf else 0.0

        # Try bbox dict or list of numbers
        nums = None
        m_bbox_dict = re.search(r'"bbox"\s*:\s*\{([^}]*)\}', btxt)
        m_bbox_list = re.search(r'"bbox"\s*:\s*\[([^\]]*)\]', btxt)
        if m_bbox_list:
            nums = re.findall(r'-?\d+\.?\d*', m_bbox_list.group(1))
        elif m_bbox_dict:
            nums = re.findall(r'-?\d+\.?\d*', m_bbox_dict.group(1))
        if not nums or len(nums) < 4:
            continue
        try:
            x1, y1, x2, y2 = [float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])]
        except ValueError:
            continue

        values = _normalize_bbox([x1, y1, x2, y2], width, height)
        if any(v < 0 or v > 1 for v in values):
            continue
        detections.append({
            "label": label,
            "confidence": conf,
            "bbox": {"left": values[0], "top": values[1], "right": values[2], "bottom": values[3]},
        })
    return detections


def run_vlm_on_frame(client: OpenAI, model_id: str, image_path: Path, max_side: int = 0) -> list[dict[str, Any]]:
    with image_path.open("rb") as f:
        img_bytes = f.read()

    data_bytes = img_bytes
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    width: int | None
    height: int | None

    # Attempt to decode and optionally downscale for heavyweight models
    try:
        img = cv2.imdecode(np.frombuffer(img_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        img = None

    if img is not None:
        height, width = img.shape[0], img.shape[1]
        if max_side and max(height, width) > max_side:
            scale = max_side / float(max(height, width))
            new_w = max(1, int(round(width * scale)))
            new_h = max(1, int(round(height * scale)))
            resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            height, width = resized.shape[0], resized.shape[1]
            success, encoded = cv2.imencode(
                ".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            )
            if success:
                data_bytes = encoded.tobytes()
                mime = "image/jpeg"
                print(
                    f"Resized {image_path.name} to {width}x{height} (max-side {max_side}) for VLM input"
                )
            else:
                # fall back to original bytes if encoding fails
                height, width = img.shape[0], img.shape[1]
    else:
        width = height = None

    b64 = base64.b64encode(data_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": USER_PROMPT_TEMPLATE},
                # LM Studio's OpenAI-compatible API expects 'image_url' content. Use a base64 data URL.
                {"type": "image_url", "image_url": data_url},
            ],
        },
    ]
    try:
        resp = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0,
        )
    except BadRequestError as e:
        msg = str(e)
        # If server insists on image_url object shape, retry once with nested form
        if "image_url" in msg and ("object" in msg or "must be an object" in msg):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT_TEMPLATE},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ]
            resp = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0,
            )
        else:
            # Surface a clearer error when the model identifier is invalid or the local server rejects the request
            raise RuntimeError(f"VLM request failed: {e}") from e

    # Print response for debugging (truncated to avoid noise)
    try:
        raw_content = (resp.choices[0].message.content or "")
        print(f"VLM response model: {getattr(resp, 'model', '')}")
        print(f"VLM finish_reason: {getattr(resp.choices[0], 'finish_reason', '')}")
        print("VLM raw content (first 300 chars):")
        print(_truncate(raw_content, 300))
        try:
            raw_json = json.dumps(resp.model_dump(), ensure_ascii=False)
            print("VLM full response (truncated 2000 chars):")
            print(_truncate(raw_json, 2000))
        except Exception:
            pass
    except Exception:
        pass
    text = (resp.choices[0].message.content or "").strip()
    data_text = extract_json_only(text)
    try:
        payload = json.loads(data_text)
        dets = coerce_detections(payload, width=width, height=height)
        if dets:
            return dets
    except json.JSONDecodeError:
        pass
    # Fallback regex-based parsing
    return parse_detections_from_text(text, width=width, height=height)


def main() -> None:
    args = parse_args()
    client = OpenAI(base_url=args.base_url, api_key=os.getenv("OPENAI_API_KEY", "lm-studio"))

    # Discover models if requested, or validate the provided model id
    try:
        models_resp = client.models.list()
        available_model_ids = [m.id for m in getattr(models_resp, "data", [])]
    except Exception:
        available_model_ids = []

    if args.list_models:
        if available_model_ids:
            print("Available models:")
            for mid in available_model_ids:
                print(f" - {mid}")
        else:
            print("Could not retrieve model list from LM Studio. Ensure it is running at the base URL.")
        return

    if available_model_ids and args.model_id not in available_model_ids:
        print(f"Model '{args.model_id}' not found.")
        print("Available models:")
        for mid in available_model_ids:
            print(f" - {mid}")
        print("Set --model-id to one of the above, or export LMSTUDIO_MODEL_ID.")
        return

    app = create_app()
    with app.app_context():
        run = InferenceRun.query.filter_by(id=args.run_id).first()
        if not run:
            print(f"Run {args.run_id} not found")
            return
        frames = (run.results or {}).get("frames") or []
        if not frames:
            print(f"Run {args.run_id} has no frames in results")
            return

        out_root = Path("reports") / f"run_{args.run_id}"
        json_dir = out_root / "json"
        frames_dir = out_root / "frames"
        json_dir.mkdir(parents=True, exist_ok=True)
        frames_dir.mkdir(parents=True, exist_ok=True)

        processed = 0
        for frame in frames:
            if processed >= args.limit:
                break
            image_path = Path(frame.get("image_path") or "")
            if not image_path.exists():
                # Attempt to resolve relative to project root
                candidate = PROJECT_ROOT / image_path
                image_path = candidate if candidate.exists() else image_path
            if not image_path.exists():
                continue

            detections = run_vlm_on_frame(client, args.model_id, image_path, max_side=args.max_side)
            # Tag as Model B for overlay color
            overlay_dets = [{**det, "model_id": "B"} for det in detections]

            idx = int(frame.get("index") or processed)
            overlay_out = frames_dir / f"frame_{idx:06}_overlay.png"
            json_out = json_dir / f"model_B_frame_{idx:06}.json"

            # Save JSON
            with json_out.open("w") as f:
                json.dump({
                    "runId": args.run_id,
                    "frameId": idx,
                    "model": "B",
                    "detections": detections,
                }, f, indent=2)

            # Draw overlay and save
            try:
                draw_frame_overlay(image_path, overlay_dets, overlay_out)
            except Exception as e:
                print(f"Overlay failed for frame {idx}: {e}")

            print(f"Processed frame {idx}: {len(detections)} detections")
            processed += 1

        print(f"Done. Outputs in {out_root}")


if __name__ == "__main__":
    main()
