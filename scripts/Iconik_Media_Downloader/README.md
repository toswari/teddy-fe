# Iconik Media Downloader

Automated script to download all videos and images from Iconik share URLs.

## Requirements

- Python 3.7+
- Playwright with Chromium browser

## Installation

```powershell
pip install playwright requests
python -m playwright install chromium
```

## Usage

```powershell
python iconik_network_intercept.py <share_url> <output_folder>
```

### Example

```powershell
python iconik_network_intercept.py "https://icnk.io/u/-HlYaqS3Mdnm/" "Customer_Provided_Data"
```

## How It Works

1. Opens the Iconik share page in a browser
2. Intercepts network requests to capture signed download URLs
3. Clicks through each asset to trigger video loading
4. Downloads all intercepted video files with progress tracking

## Features

- ✅ Fully automated - no manual interaction required
- ✅ Handles browser authentication automatically
- ✅ Progress tracking for each download
- ✅ Automatic filename conflict resolution
- ✅ Works with short URLs (icnk.io) and full URLs

## Output

Downloaded files are saved to the specified output folder with their original filenames.
