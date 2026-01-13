from pathlib import Path
import cv2
import numpy as np

from app.services.reporting_service import draw_frame_overlay

# Create a synthetic test image
h, w = 360, 640
img = np.full((h, w, 3), 255, dtype=np.uint8)
input_path = Path("tmp/runtime/test_frame.png")
input_path.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(input_path), img)

# Sample detections for Model A and B
detections = [
    {
        "model_id": "A",
        "label": "BrandX",
        "confidence": 0.94,
        "bbox": {"left": 0.2, "top": 0.2, "right": 0.5, "bottom": 0.45},
    },
    {
        "model_id": "B",
        "label": "BrandY",
        "confidence": 0.88,
        "bbox": {"left": 0.55, "top": 0.3, "right": 0.85, "bottom": 0.7},
    },
]

output_path = Path("reports/run_43/frames/frame_000043_overlay.png")
result = draw_frame_overlay(input_path, detections, output_path)
print(f"Overlay generated at: {result}")
