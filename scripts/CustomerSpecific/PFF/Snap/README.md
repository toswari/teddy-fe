# Moment of Snap Detection

A computer vision system for automatically detecting the moment of snap in American football videos.

## Features

- Automatic detection of the moment when the ball is snapped
- Yard line detection for region of interest identification
- Motion analysis using optical flow
- Visualization tools for debugging and analysis
- Output includes frames around the snap, motion plots, and temporal analysis

## Installation


1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the demo script to process a sample video:

```bash
python demo.py
```

The script will:
- Process the input video
- Detect yard lines
- Analyze motion patterns
- Identify the moment of snap
- Generate visualization outputs in the `output_frames` directory

### Output Files

The following files will be generated in the `output_frames` directory:
- `motion_differences_plot.png`: Plot of motion differences over time
- `vti_heatmap.png`: Vertical temporal image visualization
- `motion_diffs.txt`: Raw motion difference data
- Frame images around the detected snap moment
