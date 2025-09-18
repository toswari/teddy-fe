# 🟦 ClarifaiAgent.md

## Clarifai Agent Guidance: Image Input & Compliance Validation

This document provides step-by-step instructions for agents to make Clarifai API calls for image-based logo detection and compliance validation, supporting both local and remote image inputs.

---

## 1. Image Input Preparation

- **Supported Formats:** JPEG, PNG, BMP, GIF
- **Input Types:**
  - Local file (read as bytes)
  - Image URL (publicly accessible)
  - Base64-encoded string

---

## 2. Clarifai API Client Setup

- Use the official Clarifai Python SDK (`clarifai-grpc` recommended)
- Authenticate with your API key

---

## 3. Making a Call for Local Image Input

```python
# Read local image as bytes
with open("path/to/your_image.jpg", "rb") as f:
    image_bytes = f.read()

# Build and send the request
response = stub.PostModelOutputs(
    service_pb2.PostModelOutputsRequest(
        model_id="logo-detection-advconfig",
        inputs=[
            resources_pb2.Input(
                data=resources_pb2.Data(
                    image=resources_pb2.Image(
                        base64=image_bytes
                    )
                )
            )
        ]
    ),
    metadata=metadata
)
```

---

## 4. Making a Call for Image URL Input

```python
image_url = "https://example.com/image.jpg"

response = stub.PostModelOutputs(
    service_pb2.PostModelOutputsRequest(
        model_id="logo-detection-advconfig",
        inputs=[
            resources_pb2.Input(
                data=resources_pb2.Data(
                    image=resources_pb2.Image(
                        url=image_url
                    )
                )
            )
        ]
    ),
    metadata=metadata
)
```

---

## 5. Parsing the Response

- Extract detection results, bounding boxes, and compliance scores from `response.outputs`
- Validate against official logo standards:
  - **Aspect Ratio:** 3.45:1 (±10% tolerance)
  - **Color Accuracy:** 80% minimum compliance threshold
  - **Size Validation:** Minimum size requirements
  - **Overall Score:** 0-100% compliance rating

---

## 6. Error Handling

- Check for `response.status.code == SUCCESS`
- Handle API/network errors gracefully

---

## 7. Rule Execution Priority (for compliance)

1. **Priority 0:** Official Logo Validation (NEW)
2. **Priority 1:** Core measurement rules
3. **Priority 2:** Layout and spacing rules
4. **Priority 3:** Color and style rules
5. **Priority 4:** Partnership and collaboration rules

---

## References
- [Clarifai Python SDK Docs](https://docs.clarifai.com/api-guide/predict/images)
- Model: `logo-detection-advconfig`
- Input: image bytes or URL

---

**This guidance enables agents to perform Clarifai image detection and compliance validation for KIA brand guidelines.**
