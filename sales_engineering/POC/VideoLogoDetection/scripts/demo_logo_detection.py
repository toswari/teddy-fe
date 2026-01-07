"""Quick smoke-test script for Clarifai logo detection models.

Usage examples:
    python scripts/demo_logo_detection.py --image-url https://samples.clarifai.com/metro-north.jpg
    python scripts/demo_logo_detection.py --image-file ./data/frame.jpg

Relies on the CLARIFAI_PAT environment variable and defaults to Clarifai's
public logo detector unless overridden with CLI flags or environment vars.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from dotenv import load_dotenv

DEFAULT_IMAGE_URL = "https://samples.clarifai.com/metro-north.jpg"
DEFAULT_MODEL_ID = "logo-detection-v2"
DEFAULT_MODEL_VERSION_ID = "09f3acb13bde404592c81254c5d87ae1"
DEFAULT_USER_ID = "clarifai"
DEFAULT_APP_ID = "main"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Clarifai logo detection once.")
    parser.add_argument("--image-url", dest="image_url", help="Image URL to analyze.")
    parser.add_argument(
        "--image-file",
        dest="image_file",
        help="Local image to analyze (overrides image URL).",
    )
    parser.add_argument(
        "--model-id",
        dest="model_id",
        default=os.getenv("CLARIFAI_MODEL_ID", DEFAULT_MODEL_ID),
        help="Clarifai model ID (default: %(default)s)",
    )
    parser.add_argument(
        "--model-version-id",
        dest="model_version_id",
        default=os.getenv("CLARIFAI_MODEL_VERSION_ID", DEFAULT_MODEL_VERSION_ID),
        help="Clarifai model version ID (default: %(default)s)",
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        default=os.getenv("CLARIFAI_USER_ID", DEFAULT_USER_ID),
        help="Clarifai user ID (default: %(default)s)",
    )
    parser.add_argument(
        "--app-id",
        dest="app_id",
        default=os.getenv("CLARIFAI_APP_ID", DEFAULT_APP_ID),
        help="Clarifai app ID (default: %(default)s)",
    )
    return parser.parse_args()


def load_image_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    with open(path, "rb") as infile:
        return infile.read()


def run_logo_detection(
    *,
    pat: str,
    user_id: str,
    app_id: str,
    model_id: str,
    model_version_id: str,
    image_url: str | None,
    image_bytes: bytes | None,
) -> Iterable[str]:
    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    metadata = (("authorization", "Key " + pat),)
    user_data = resources_pb2.UserAppIDSet(user_id=user_id, app_id=app_id)

    image_data = resources_pb2.Image()
    if image_bytes:
        image_data.base64 = image_bytes
    elif image_url:
        image_data.url = image_url
    else:
        raise ValueError("Either image bytes or image URL must be provided")

    response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            user_app_id=user_data,
            model_id=model_id,
            version_id=model_version_id,
            inputs=[resources_pb2.Input(data=resources_pb2.Data(image=image_data))],
        ),
        metadata=metadata,
    )

    if response.status.code != status_code_pb2.SUCCESS:
        raise RuntimeError(
            f"PostModelOutputs failed: code={response.status.code} desc={response.status.description}"
        )

    detections = []
    for region in response.outputs[0].data.regions:
        bbox = region.region_info.bounding_box
        coords = (
            round(bbox.top_row, 3),
            round(bbox.left_col, 3),
            round(bbox.bottom_row, 3),
            round(bbox.right_col, 3),
        )
        for concept in region.data.concepts:
            detections.append(
                f"{concept.name}: {concept.value:.4f} bbox={coords[0]}, {coords[1]}, {coords[2]}, {coords[3]}"
            )
    return detections


def main() -> int:
    # Ensure values from .env (if present) are loaded before reading env vars.
    load_dotenv()
    args = parse_args()
    pat = os.getenv("CLARIFAI_PAT")
    if not pat:
        print("CLARIFAI_PAT environment variable is required", file=sys.stderr)
        return 1

    image_bytes = load_image_bytes(args.image_file)
    image_url = args.image_url or os.getenv("CLARIFAI_TEST_IMAGE", DEFAULT_IMAGE_URL)

    try:
        detections = run_logo_detection(
            pat=pat,
            user_id=args.user_id,
            app_id=args.app_id,
            model_id=args.model_id,
            model_version_id=args.model_version_id,
            image_url=image_url,
            image_bytes=image_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Clarifai request failed: {exc}", file=sys.stderr)
        return 1

    if not detections:
        print("No logo detections returned.")
        return 0

    print("Detections:")
    for line in detections:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
