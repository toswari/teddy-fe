# Dynamic MPEG-DASH Implementation

## Overview
Implemented full support for dynamic/live MPEG-DASH manifests according to ISO/IEC 23009-1:2012 standard with `isoff-live:2011` profile.

## Features Implemented

### 1. Backend Support (`backend/main.py`)
- ✅ Dynamic manifest generation with `type="dynamic"`
- ✅ Segment window management (`window_size`, `extra_window_size`)
- ✅ Manifest update period configuration
- ✅ Time-shift buffer (DVR capability)
- ✅ Post-processing to add live streaming attributes:
  - `availabilityStartTime` - When the stream became available
  - `publishTime` - Current manifest generation time
  - `minimumUpdatePeriod` - Player manifest refresh interval
  - `suggestedPresentationDelay` - Latency buffer
  - `timeShiftBufferDepth` - DVR rewind window

### 2. UI Support (`ui/streamlit_app.py`)
- ✅ Checkbox to enable dynamic/live mode
- ✅ Live streaming options panel (conditional display)
- ✅ Configuration fields:
  - Minimum update period (default: 8s)
  - Suggested presentation delay (default: 8s)
  - Time-shift buffer depth (default: 3600s / 1 hour)
  - Window size and extra window size
- ✅ Help tooltips explaining each option

### 3. API Parameters

```python
{
  "mode": "dynamic",  # "static" or "dynamic"
  "segment_duration_seconds": 4.0,
  "window_size": 6,
  "extra_window_size": 6,
  "minimum_update_period": 8.0,
  "suggested_presentation_delay": 8.0,
  "time_shift_buffer_depth": 3600.0
}
```

## Usage

### Via UI
1. Open Streamlit app
2. Go to "Manage Streams"
3. Check "Show advanced packaging options"
4. Check "Produce dynamic/live MPD"
5. Configure live streaming parameters:
   - Update period: How often players refresh manifest
   - Presentation delay: Latency buffer
   - Time-shift buffer: DVR window duration
6. Click "Package to DASH"

### Via API
```bash
curl -X POST http://localhost:8000/api/dash/package \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/path/to/video.mp4",
    "stream_id": "stream123",
    "options": {
      "mode": "dynamic",
      "segment_duration_seconds": 4.0,
      "window_size": 6,
      "extra_window_size": 6,
      "minimum_update_period": 8.0,
      "suggested_presentation_delay": 8.0,
      "time_shift_buffer_depth": 3600.0
    }
  }'
```

## Generated MPD Example

```xml
<?xml version="1.0" encoding="utf-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"
     profiles="urn:mpeg:dash:profile:isoff-live:2011"
     type="dynamic"
     minimumUpdatePeriod="PT8S"
     suggestedPresentationDelay="PT8S"
     timeShiftBufferDepth="PT3600S"
     availabilityStartTime="2026-01-28T19:11:12.317Z"
     publishTime="2026-01-28T19:11:12.317Z"
     maxSegmentDuration="PT4.0S"
     minBufferTime="PT16.6S">
  ...
</MPD>
```

## Standard Compliance

- **Standard**: ISO/IEC 23009-1:2012 (MPEG-DASH)
- **Profile**: `urn:mpeg:dash:profile:isoff-live:2011`
- **Type**: `dynamic` (live streaming)
- **Compatible with**: dash.js, Shaka Player, ExoPlayer, HLS.js

## Technical Notes

### FFmpeg Limitations
FFmpeg's DASH muxer doesn't natively support all live streaming attributes when packaging VoD content. Our implementation works around this by:

1. Using FFmpeg's `-streaming 1 -ldash 1` flags for segment windowing
2. Post-processing the generated MPD to add missing attributes
3. Converting `type="static"` to `type="dynamic"`
4. Adding temporal metadata (`availabilityStartTime`, `publishTime`)

### Live Simulation vs True Live
This implementation creates a "simulated live" experience from VoD files:
- **True Live**: Continuous stream from live source (camera, encoder)
- **Simulated Live**: VoD content presented as live with rolling window and DVR

For true live streaming from a camera/encoder, you would:
1. Use a proper live encoder (e.g., OBS, FFmpeg with live input)
2. Stream to the packager in real-time
3. The packager generates manifests dynamically as segments arrive

## Testing

Test script provided: `test-dynamic-dash.sh`
Conversion utility: `convert_mpd_to_dynamic.py`

```bash
# Test dynamic packaging
./test-dynamic-dash.sh

# Convert existing static MPD to dynamic
python convert_mpd_to_dynamic.py path/to/manifest.mpd 8 8 3600
```

## References

- ISO/IEC 23009-1:2012 - MPEG-DASH Standard
- https://dashif.org/ - DASH Industry Forum
- https://standards.iso.org/ittf/PubliclyAvailableStandards/MPEG-DASH_schema_files/
