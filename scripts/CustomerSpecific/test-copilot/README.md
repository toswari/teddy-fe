# Test-Copilot MM-Poly-8B Examples

This directory contains example scripts for using the Clarifai MM-Poly-8B model in various ways.

## Prerequisites

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your Clarifai Personal Access Token (PAT) as an environment variable:
```bash
export CLARIFAI_PAT="your_pat_token_here"
```

## Available Scripts

### 1. OpenAI-Compatible API Usage (`openai_compatible_api.py`)
Demonstrates how to use the MM-Poly-8B model via Clarifai's OpenAI-compatible API endpoint.

```bash
python openai_compatible_api.py
```

### 2. Text Prediction (`predict_text.py`)
Shows how to use the model for text-based predictions.

```bash
python predict_text.py
```

### 3. Image Prediction (`predict_image.py`)
Demonstrates image analysis with the MM-Poly-8B model.

```bash
python predict_image.py
```

### 4. Audio Prediction (`predict_audio.py`)
Shows how to analyze audio files with the model.

```bash
python predict_audio.py
```

### 5. Video Prediction (`predict_video.py`)
Demonstrates video analysis capabilities.

```bash
python predict_video.py
```

### 6. Streaming/Generate (`streaming_generate.py`)
Shows how to use the model with streaming responses.

```bash
python streaming_generate.py
```

## Model Information

The MM-Poly-8B model is a multimodal AI model that can process:
- Text
- Images
- Audio
- Video

Model URL: `https://clarifai.com/clarifai/main/models/mm-poly-8b`

## Notes

- All scripts require a valid Clarifai PAT token set in the `CLARIFAI_PAT` environment variable
- The scripts use sample data from Clarifai's public samples
- You can modify the prompts and inputs to suit your specific use cases

## Support

For issues or questions, please refer to the [Clarifai Documentation](https://docs.clarifai.com).
