import cv2
import numpy as np
import glob
from natsort import natsorted
import os

def load_frames(frame_dir):
    """Load frames from directory in natural order"""
    frame_paths = natsorted(glob.glob(os.path.join(frame_dir, "*.jpg")))
    frames = []
    for path in frame_paths:
        frame = cv2.imread(path)
        if frame is not None:
            frames.append(frame)
    return frames

def calibrate_green_color(frames, sample_size=50):
    """Calibrate green color range from field frames (Section 3.1)"""
    # Sample frames to estimate green color range
    sample_frames = frames[::max(1, len(frames)//sample_size)]
    
    green_pixels = []
    for frame in sample_frames:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Initial broad green range
        mask = cv2.inRange(hsv, (35, 40, 40), (85, 255, 255))
        green_pixels.extend(hsv[mask > 0][:, 0])  # Hue values
    
    if len(green_pixels) > 0:
        green_pixels = np.array(green_pixels)
        g_mean = np.mean(green_pixels)
        g_std = np.std(green_pixels)
        g_low = max(35, g_mean - 2*g_std)
        g_high = min(85, g_mean + 2*g_std)
        return int(g_low), int(g_high)
    
    return 45, 75  # Default green range

def detect_field_frame(frame, g_low, g_high, green_threshold=0.3):
    """Detect if frame contains football field (Section 3.1)"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    
    # Focus on center region to avoid scoreboards/borders
    center_y1, center_y2 = h//4, 3*h//4
    center_x1, center_x2 = w//6, 5*w//6
    center_region = hsv[center_y1:center_y2, center_x1:center_x2]
    
    # Check for green pixels in center region
    green_mask = cv2.inRange(center_region, (g_low, 40, 40), (g_high, 255, 255))
    green_ratio = np.sum(green_mask > 0) / green_mask.size
    
    return green_ratio > green_threshold

def detect_field_lines(frame, g_low, g_high):
    """Detect field lines on green background (Section 3.1)"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create green mask
    green_mask = cv2.inRange(hsv, (g_low, 40, 40), (g_high, 255, 255))
    
    # Edge detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    
    # Filter edges to only green background
    edges_on_green = cv2.bitwise_and(edges, green_mask)
    
    # Hough line detection
    lines = cv2.HoughLinesP(edges_on_green, 1, np.pi/180, 
                           threshold=50, minLineLength=50, maxLineGap=10)
    
    return lines is not None and len(lines) >= 3

def check_player_lineup(frame, g_low, g_high):
    """Check for player lineup formation (Section 3.1)"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    
    # Create inverse green mask (non-field objects)
    green_mask = cv2.inRange(hsv, (g_low, 40, 40), (g_high, 255, 255))
    non_green_mask = cv2.bitwise_not(green_mask)
    
    # Focus on center horizontal band where players line up
    center_y = h // 2
    band_height = h // 6
    lineup_region = non_green_mask[center_y-band_height:center_y+band_height, :]
    
    # Project to x-axis to find player positions
    x_projection = np.sum(lineup_region, axis=0)
    
    # Find peaks (player positions)
    peaks = []
    threshold = np.max(x_projection) * 0.3
    for i in range(1, len(x_projection)-1):
        if (x_projection[i] > threshold and 
            x_projection[i] > x_projection[i-1] and 
            x_projection[i] > x_projection[i+1]):
            peaks.append(i)
    
    # Check for reasonable number of players lined up
    return len(peaks) >= 8 and len(peaks) <= 15

def check_minimal_motion(frame, prev_frame):
    """Check for minimal motion before snap (Section 3.1)"""
    if prev_frame is None:
        return True
    
    # Calculate frame difference
    gray1 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    
    diff = cv2.absdiff(gray1, gray2)
    motion_pixels = np.sum(diff > 30)
    total_pixels = diff.size
    
    motion_ratio = motion_pixels / total_pixels
    return motion_ratio < 0.1  # Low motion threshold

def detect_snap_candidates(frames, g_low, g_high, window_size=5):
    """Detect potential snap moments using temporal evidence (Section 3.1)"""
    candidates = []
    
    for i in range(len(frames)):
        frame = frames[i]
        prev_frame = frames[i-1] if i > 0 else None
        
        # Check all conditions for snap detection
        is_field = detect_field_frame(frame, g_low, g_high)
        has_lines = detect_field_lines(frame, g_low, g_high)
        has_lineup = check_player_lineup(frame, g_low, g_high)
        low_motion = check_minimal_motion(frame, prev_frame)
        
        # Score based on conditions met
        score = sum([is_field, has_lines, has_lineup, low_motion])
        
        if score >= 3:  # At least 3 conditions met
            candidates.append((i, score))
    
    return candidates

def apply_temporal_filtering(candidates, window_size=15, min_evidence=0.7):
    """Apply temporal evidence accumulation (Section 3.1, Figure 19)"""
    if not candidates:
        return []
    
    snap_moments = []
    candidate_frames = [c[0] for c in candidates]
    
    for i, (frame_idx, score) in enumerate(candidates):
        # Check window around this candidate
        window_start = max(0, i - window_size//2)
        window_end = min(len(candidates), i + window_size//2 + 1)
        
        window_candidates = candidate_frames[window_start:window_end]
        window_range = range(frame_idx - window_size//2, frame_idx + window_size//2 + 1)
        
        # Count evidence in window
        evidence_count = sum(1 for c in window_candidates if c in window_range)
        evidence_ratio = evidence_count / window_size
        
        if evidence_ratio >= min_evidence:
            snap_moments.append(frame_idx)
    
    # Remove nearby detections (within 30 frames)
    filtered_snaps = []
    for snap in snap_moments:
        if not filtered_snaps or snap - filtered_snaps[-1] > 30:
            filtered_snaps.append(snap)
    
    return filtered_snaps

def main():
    """Main snap detection pipeline"""
    frame_dir = "/Users/bingqingyu/work/PS-Field-Engineering/scripts/CustomerSpecific/PFF/cyu_test/frames_ez"  # Directory containing 0001.jpg, 0002.jpg, etc.
    
    print("Loading frames...")
    frames = load_frames(frame_dir)
    if not frames:
        print("No frames found!")
        return
    
    print(f"Loaded {len(frames)} frames")
    
    # Step 1: Calibrate green color from video
    print("Calibrating green color...")
    g_low, g_high = calibrate_green_color(frames)
    print(f"Green range: {g_low}-{g_high}")
    
    # Step 2: Detect snap candidates
    print("Detecting snap candidates...")
    candidates = detect_snap_candidates(frames, g_low, g_high)
    print(f"Found {len(candidates)} initial candidates")
    
    # Step 3: Apply temporal filtering
    print("Applying temporal filtering...")
    snap_moments = apply_temporal_filtering(candidates)
    
    print(f"\nDetected snap moments at frames: {snap_moments}")
    
    # Convert to timestamps (assuming 30 fps)
    fps = 30
    for frame_num in snap_moments:
        timestamp = frame_num / fps
        print(f"Snap at frame {frame_num:04d} (time: {timestamp:.2f}s)")

if __name__ == "__main__":
    main()
