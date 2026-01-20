# Image Content Moderation Processor

A Python script for batch processing image URLs through VLM (`mm-poly-8b`) for content moderation and classification.

## Overview

`process.py` is a command-line tool that:

- Reads image URLs from CSV or text files
- Downloads and preprocesses images (resize, format conversion)
- Sends images to Clarifai's AI model with a customizable prompt
- Classifies images into brand safety categories
- Outputs results in JSON/JSONL and CSV formats

## Requirements

### Dependencies

```bash
pip install clarifai requests pillow tqdm
```

### Files

| File | Description |
|------|-------------|
| `config.json` | Model configuration (API credentials, endpoints, parsing rules) |
| `prompt.txt` | Content moderation prompt/taxonomy definition |

## Usage

### Basic Usage

```bash
python process.py --input urls.csv --url-col "Image URL" --out results.jsonl
```

### Examples

```bash
# Process CSV with custom URL column
python process.py --input urls.csv --url-col "Image URL" --out results.json

# Process plain text file of URLs
python process.py --input urls.txt --out results.json --prompt prompt.txt

# Limit processing and adjust concurrency
python process.py --input urls.csv --limit 50 --concurrency 4

# Output to both JSONL and CSV
python process.py --input data.csv --out results.jsonl --csv-out results.csv

# Enable debug mode (saves raw model responses)
python process.py --input urls.csv --out results.jsonl --debug --debug-raw-dir debug_raw
```

## Command Line Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--input` | `-i` | *required* | Input CSV or text file containing URLs |
| `--url-col` | | `Image URL` | Column name containing URLs (CSV only) |
| `--out` | `-o` | `results.jsonl` | Output file path (.jsonl or .json) |
| `--json-array` | | `false` | Write as single JSON array instead of JSONL |
| `--csv-out` | | *none* | Optional CSV output path (in addition to JSON) |
| `--prompt` | | *none* | Inline prompt text override |
| `--prompt-file` | | *none* | Path to prompt file |
| `--config` | | `config.json` | Path to config.json |
| `--concurrency` | `-c` | `4` | Number of worker threads |
| `--limit` | | *none* | Limit number of URLs processed |
| `--progress/--no-progress` | | `true` | Show/hide progress bar |
| `--debug` | | `false` | Enable debug mode (store raw outputs) |
| `--debug-raw-dir` | | `debug_raw` | Directory for raw debug outputs |

## Input Formats

### CSV File
```csv
Image URL,Title,Author
https://example.com/image1.jpg
https://example.com/image2.jpg
```

### Text File (.txt or .list)
```
https://example.com/image1.jpg
https://example.com/image2.jpg
https://example.com/image3.jpg
```

## Output Format

### JSONL Output
Each line contains a JSON object:
```json
{
  "index": 0,
  "url": "https://example.com/image.jpg",
  "model": "mm-poly-8b",
  "result": "Okay_Illustrated (0.95)",
  "reasoning": "The image shows a simple book cover with text and abstract design...",
  "text_found": "Book Title",
  "latency_s": 2.45,
  "error": null
}
```

### CSV Output
When using `--csv-out`, includes original CSV columns merged with prediction results.

## Configuration

### config.json Structure

```json
{
  "models": [
    {
      "name": "mm-poly-8b",
      "url": "https://clarifai.com/clarifai/main/models/mm-poly-8b",
      "pat": "YOUR_API_KEY",
      "user_id": "your_user_id",
      "response_map": "...",
      "reasoning_map": "...",
      "resize_to": 1200,
      "needs_prompt": true,
      "enabled": true,
      "timeout": 10
    }
  ]
}
```

### Model Configuration Fields

| Field | Description |
|-------|-------------|
| `name` | Model identifier |
| `url` | Clarifai model URL |
| `pat` | Personal Access Token for Clarifai API |
| `user_id` | Clarifai user ID |
| `response_map` | Python expression to extract prediction result |
| `reasoning_map` | Python expression to extract reasoning |
| `resize_to` | Max dimension for image resizing (preserves aspect ratio) |
| `needs_prompt` | Whether model requires prompt input |
| `timeout` | Request timeout in seconds |

## Content Classification Categories

The model classifies images into the following categories (defined in `prompt.txt`):

### Brand Safe
- `Okay_Illustrated` - G-rated illustrated content
- `Okay_Realistic` - G-rated realistic/photo content

### Brand-Risky
- `Romantic_Illustrated` / `Romantic_Realistic` - Non-sexual affection
- `Sexy_Illustrated` / `Sexy_Realistic` - Suggestive but non-explicit
- `Violence_Illustrated_Mature` / `Violence_Realistic_Mature` - Moderate violence
- `SelfHarm_Illustrated_Everyone` / `SelfHarm_Realistic_Everyone` - Self-harm context

### Not Brand Safe
- `CSEM` - Child sexual exploitation material
- `Explicit_Illustrated_Porn` / `Explicit_Realistic_Porn` - Explicit content
- `Violence_Illustrated_Banned` / `Violence_Realistic_Banned` - Graphic violence
- `SelfHarm_Illustrated_Banned` / `SelfHarm_Realistic_Banned` - Graphic self-harm

## Features

- **Concurrent Processing**: Multi-threaded image download and prediction
- **Automatic Retries**: Built-in retry logic for failed downloads/predictions
- **Image Preprocessing**: Automatic resize and format conversion (to JPEG)
- **Progress Tracking**: Real-time progress bar with tqdm
- **Debug Mode**: Save raw model responses for troubleshooting
- **Flexible Output**: Support for JSONL, JSON array, and CSV formats
- **Graceful Error Handling**: Continues processing on individual failures

## Error Handling

The script handles errors gracefully:
- Failed image downloads are logged with error details
- Prediction timeouts are captured and reported
- Processing continues even if individual images fail
- Summary statistics show error counts at completion

## Debug Mode

Enable debug mode to save raw model outputs:

```bash
python process.py --input urls.csv --debug --debug-raw-dir debug_raw
```

Raw responses are saved as numbered JSON files in the specified directory:
- `debug_raw/raw_0000.json`
- `debug_raw/raw_0001.json`
- etc.

## Summary Output

After processing, the script displays:
```
Summary:
  Total: 100
  Errors: 2 (2.0%)
  Avg latency: 3.45s
```

## License

Internal use only.
