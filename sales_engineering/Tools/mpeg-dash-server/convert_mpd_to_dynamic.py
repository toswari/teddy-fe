#!/usr/bin/env python3
"""
Post-process a static MPEG-DASH manifest to convert it to dynamic/live mode.
This adds the necessary attributes for live streaming simulation from VoD content.
"""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def convert_to_dynamic(mpd_path: Path, update_period: int = 8,
                      presentation_delay: int = 8, time_shift_buffer: int = 3600):
    """Convert static MPD to dynamic with live streaming attributes"""
    
    # Parse the MPD
    ET.register_namespace('', 'urn:mpeg:dash:schema:mpd:2011')
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    
    tree = ET.parse(mpd_path)
    root = tree.getroot()
    
    # Change type from static to dynamic
    root.set('type', 'dynamic')
    
    # Remove mediaPresentationDuration (not used in dynamic manifests)
    if 'mediaPresentationDuration' in root.attrib:
        del root.attrib['mediaPresentationDuration']
    
    # Add live streaming attributes
    root.set('minimumUpdatePeriod', f'PT{update_period}S')
    root.set('suggestedPresentationDelay', f'PT{presentation_delay}S')
    root.set('timeShiftBufferDepth', f'PT{time_shift_buffer}S')
    
    # Add availability start time (current time minus buffer)
    # This simulates the stream having been live for a while
    avail_start = datetime.now(timezone.utc)
    root.set('availabilityStartTime', avail_start.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
    
    # Add publish time (current time)
    publish_time = datetime.now(timezone.utc)
    root.set('publishTime', publish_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z')
    
    # Write back with proper formatting
    tree.write(mpd_path, encoding='utf-8', xml_declaration=True)
    
    print(f"✅ Converted {mpd_path} to dynamic mode")
    print(f"   - Type: dynamic")
    print(f"   - Update Period: {update_period}s")
    print(f"   - Presentation Delay: {presentation_delay}s")
    print(f"   - Time-Shift Buffer: {time_shift_buffer}s ({time_shift_buffer//3600}h {(time_shift_buffer%3600)//60}m)")
    print(f"   - Availability Start: {avail_start.isoformat()}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python convert_mpd_to_dynamic.py <manifest.mpd> [update_period] [presentation_delay] [time_shift_buffer]")
        print("Example: python convert_mpd_to_dynamic.py manifest.mpd 8 8 3600")
        sys.exit(1)
    
    mpd_file = Path(sys.argv[1])
    if not mpd_file.exists():
        print(f"Error: File not found: {mpd_file}")
        sys.exit(1)
    
    update_period = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    presentation_delay = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    time_shift_buffer = int(sys.argv[4]) if len(sys.argv) > 4 else 3600
    
    convert_to_dynamic(mpd_file, update_period, presentation_delay, time_shift_buffer)
