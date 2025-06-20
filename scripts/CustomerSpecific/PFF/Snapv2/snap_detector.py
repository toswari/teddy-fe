import cv2
import numpy as np
from ultralytics import YOLO
import torch
from sklearn.cluster import DBSCAN
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from moviepy.editor import VideoFileClip, ImageSequenceClip

class SnapDetector:
    def __init__(self):
        # Initialize YOLO model for person detection
        self.model = YOLO('yolov8n.pt')
        # Parameters for motion analysis
        self.feature_params = dict(maxCorners=100,
                                 qualityLevel=0.3,
                                 minDistance=7,
                                 blockSize=7)
        self.lk_params = dict(winSize=(15, 15),
                             maxLevel=2,
                             criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        self.motion_history = []
        self.camera_motion_history = []
        
    def detect_field_points(self, frame: np.ndarray) -> np.ndarray:
        """Detect stable points on the field for camera motion tracking."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.goodFeaturesToTrack(gray, mask=None, **self.feature_params)
    
    def track_motion(self, prev_frame: np.ndarray, curr_frame: np.ndarray, 
                    prev_points: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Track motion between frames using optical flow."""
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        
        new_points, status, error = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, 
                                                            prev_points, None, 
                                                            **self.lk_params)
        return new_points, status

    def detect_players(self, frame: np.ndarray) -> List[Dict]:
        """Detect players using YOLO model."""
        results = self.model(frame, classes=[0])  # class 0 is person
        return results[0].boxes.data.cpu().numpy()

    def calculate_motion_metrics(self, players: List[Dict], 
                               prev_players: List[Dict]) -> float:
        """Calculate motion metrics for players."""
        if len(prev_players) == 0:
            return 0.0
        
        total_motion = 0
        matched_players = 0
        
        # Use DBSCAN to match players between frames
        for curr_player in players:
            curr_center = curr_player[:2]  # x, y coordinates
            min_dist = float('inf')
            
            for prev_player in prev_players:
                prev_center = prev_player[:2]
                dist = np.linalg.norm(curr_center - prev_center)
                min_dist = min(min_dist, dist)
            
            if min_dist != float('inf'):
                total_motion += min_dist
                matched_players += 1
                
        return total_motion / max(matched_players, 1)

    def detect_snap(self, video_path: str) -> Tuple[int, List[float], List[float]]:
        """
        Detect the snap moment in a football video.
        Returns frame number of snap, player motion history, and camera motion history.
        """
        # Clear motion history at the start of each video
        self.motion_history = []
        self.camera_motion_history = []
        
        cap = cv2.VideoCapture(video_path)
        prev_frame = None
        prev_players = []
        prev_points = None
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Detect players
            players = self.detect_players(frame)
            
            # Track field points for camera motion
            if prev_frame is not None:
                if prev_points is None:
                    prev_points = self.detect_field_points(prev_frame)
                
                if prev_points is not None:
                    new_points, status = self.track_motion(prev_frame, frame, prev_points)
                    if len(new_points) > 0:  # Add check for valid points
                        camera_motion = np.mean(np.linalg.norm(new_points - prev_points, axis=1))
                        self.camera_motion_history.append(camera_motion)
                        prev_points = new_points
                    else:
                        self.camera_motion_history.append(0)
                        prev_points = self.detect_field_points(frame)  # Reset points if tracking failed
            
            # Calculate player motion
            player_motion = self.calculate_motion_metrics(players, prev_players)
            self.motion_history.append(player_motion)
            
            prev_frame = frame.copy()
            prev_players = players
            frame_count += 1
            
        cap.release()
        
        # Detect snap moment using motion patterns
        snap_frame = self.analyze_motion_patterns()
        
        return snap_frame, self.motion_history, self.camera_motion_history

    def analyze_motion_patterns(self) -> int:
        """
        Analyze motion patterns to identify the snap moment.
        Returns the frame number of the detected snap.
        """
        motion_array = np.array(self.motion_history)
        camera_motion = np.array(self.camera_motion_history)
        
        # Normalize and smooth the motion data
        motion_smooth = np.convolve(motion_array, np.ones(5)/5, mode='valid')
        
        # Calculate velocity (rate of change of motion)
        velocity = np.diff(motion_smooth)
        
        # Calculate acceleration (rate of change of velocity)
        acceleration = np.diff(velocity)
        
        # Parameters for detection
        window_size = 15  # Look at more frames to ensure we catch the full motion pattern
        future_window = 30  # Look further ahead to ensure we catch the full explosion of motion
        
        # Calculate motion intensity thresholds
        motion_threshold = np.mean(motion_smooth) * 0.4  # Lower threshold for detecting quiet period
        explosion_threshold = np.percentile(motion_smooth, 85)  # High threshold for post-snap motion
        
        potential_snaps = []
        
        # Look for patterns in the valid range of frames
        for i in range(window_size, len(motion_smooth) - future_window):
            # Check for relative quiet period
            current_window = motion_smooth[i-window_size:i]
            future_window_motion = motion_smooth[i:i+future_window]
            
            # Conditions for snap detection:
            # 1. Current moment is relatively quiet
            is_quiet = np.mean(current_window) < motion_threshold
            
            # 2. Immediate future has explosive motion
            future_motion_max = np.max(future_window_motion)
            has_explosion = future_motion_max > explosion_threshold
            
            # 3. The explosion is sustained (multiple players moving)
            explosion_duration = np.sum(future_window_motion > explosion_threshold * 0.7)
            has_sustained_motion = explosion_duration > future_window * 0.3  # At least 30% of future frames have high motion
            
            # 4. The rate of motion increase is sharp
            motion_increase_rate = np.max(np.diff(future_window_motion[:10])) # Look at immediate acceleration
            
            if is_quiet and has_explosion and has_sustained_motion:
                # Score this candidate based on multiple factors
                quiet_score = 1 - (np.mean(current_window) / motion_threshold)
                explosion_score = future_motion_max / explosion_threshold
                duration_score = explosion_duration / future_window
                acceleration_score = motion_increase_rate / np.mean(np.abs(velocity))
                
                # Combine scores with weights
                total_score = (quiet_score * 0.3 + 
                             explosion_score * 0.3 + 
                             duration_score * 0.2 +
                             acceleration_score * 0.2)
                
                potential_snaps.append((i, total_score))
        
        # Return the snap moment with the highest score
        if potential_snaps:
            potential_snaps.sort(key=lambda x: x[1], reverse=True)
            return potential_snaps[0][0] + 2  # Adding offset for smoothing window
        return 0

    def create_snap_gif(self, video_path: str, snap_frame: int, 
                       output_path: str, window_size: int = 30):
        """Create a GIF around the snap moment."""
        clip = VideoFileClip(video_path)
        start_time = max(0, (snap_frame - window_size) / clip.fps)
        end_time = min(clip.duration, (snap_frame + window_size) / clip.fps)
        
        snap_clip = clip.subclip(start_time, end_time)
        snap_clip.write_gif(output_path, fps=10)
        clip.close()

    def plot_motion_graph(self, output_path: str):
        """Create a graph showing player and camera motion with snap moment."""
        plt.figure(figsize=(12, 6))
        plt.plot(self.motion_history, label='Player Motion')
        plt.plot(self.camera_motion_history, label='Camera Motion')
        plt.axvline(x=self.analyze_motion_patterns(), color='r', 
                   linestyle='--', label='Snap Moment')
        plt.xlabel('Frame Number')
        plt.ylabel('Motion Magnitude')
        plt.title('Motion Analysis for Snap Detection')
        plt.legend()
        plt.grid(True)
        plt.savefig(output_path)
        plt.close() 