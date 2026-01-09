# Model Comparison Workflow Guide

## Overview

The Model Comparison section allows you to compare inference results from different Clarifai models on the same video clip. This document explains the dropdowns and buttons in the comparison panel.

## UI Components

### 1. **Select Clip Dropdown**
- **Purpose**: Choose which video clip to run inference on or view results from
- **Populated with**: All processed clips from videos in the project
- **Format**: `VideoName · Clip # (start → end)`
- **Example**: `video_9_vision1.mp4 · Clip 1 (0:00 → 0:20)`

### 2. **Select Run Dropdown**
- **Purpose**: View results from previously completed inference runs
- **Populated with**: Existing inference runs for the selected clip
- **Format**: `Run #ID – status · timestamp`
- **Example**: `Run #5 – completed · 1/8/2026, 5:30:45 PM`
- **States**:
  - Shows "Select run" when no runs exist for the clip
  - Disabled (grayed out) if no inference runs exist
  - Auto-selects the most recent completed run when available
- **What it does**: When you select a run, it loads:
  - The frames that were analyzed
  - The detection results from each model
  - Allows you to compare model outputs side-by-side

### 3. **Model A Dropdown**
- **Purpose**: Select the first model for comparison
- **Hardcoded Options**:
  1. General Image Recognition
  2. Logo Detection (V2)
  3. Food Recognition
  4. Apparel Detection
  5. Face Detection
- **Default**: General Image Recognition
- **What it does**: Sets which model's detections appear when "Model A" toggle is active

### 4. **Model B Dropdown**
- **Purpose**: Select the second model for comparison
- **Same options as Model A**
- **Default**: Logo Detection (V2)
- **What it does**: Sets which model's detections appear when "Model B" toggle is active

### 5. **Run Inference Button**
- **Purpose**: Start a NEW inference run with the selected models
- **Action**: Sends a POST request to `/api/projects/{project_id}/videos/{video_id}/inference`
- **Required selections**:
  - Clip must be selected
  - At least one model (A or B) must be selected
- **What happens**:
  1. Validates selections
  2. Extracts frames from the clip (at 1 FPS by default)
  3. Sends frames to Clarifai API with selected models
  4. Creates a new inference run with results
  5. Shows alert with Run ID when started
  6. Updates the metrics/benchmark sections
  7. Automatically populates the "Select run" dropdown with the new run

## Typical Workflow

### View Existing Results
1. Select a clip from "Select Clip"
2. Select a run from "Select Run" (auto-populated with existing runs)
3. Toggle between "Model A" and "Model B" to compare detections
4. Use frame slider to review different frames

### Run New Inference
1. Select a clip from "Select Clip"
2. Choose models in "Model A" and "Model B" dropdowns
3. Click "Run Inference"
4. Wait for completion (watch for socket.io updates)
5. The new run will appear in "Select Run" dropdown
6. Review results using frame slider and model toggles

## Technical Details

### Inference Parameters (Hardcoded)
- **FPS**: 1.0 (extracts 1 frame per second)
- **Min Confidence**: 0.2 (20%)
- **Max Concepts**: 5 (returns top 5 detections per frame)

### Frame Navigation
- Use the frame slider to move through analyzed frames
- Click "Model A" or "Model B" buttons to switch between model views
- Detection overlays show bounding boxes and labels
- Button shows detection count: "Model A · general-image-recognition (5)"

### Real-time Updates
- WebSocket connection provides live status updates
- Metrics refresh automatically when inference completes
- Run status updates in real-time (processing → completed)

## Common Issues

### "Select run" is disabled
- **Cause**: No inference runs exist for the selected clip
- **Solution**: Click "Run Inference" to create the first run

### "Please select a clip" alert
- **Cause**: No clip selected in "Select Clip" dropdown
- **Solution**: Choose a clip that has been preprocessed

### "Please select at least one model" alert
- **Cause**: Both Model A and Model B are empty
- **Solution**: Select at least one model from the dropdowns

### Run Inference button doesn't work
- **Cause**: Missing event listener (now fixed)
- **Fix Applied**: Added click handler in `setupButtons()` function
