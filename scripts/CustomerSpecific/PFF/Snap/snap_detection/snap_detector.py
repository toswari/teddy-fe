"""
Snap detection module that combines field detection and motion analysis.
"""

from .motion_analysis import MotionAnalyzer
import numpy as np
import cv2

class SnapDetector:
    """Detects the snap of the ball in football videos."""
    
    def __init__(self, window_size=100, frame_gap=2, n_cells=10, line_of_scrimmage_region=0.2):
        """
        Initialize the snap detector.
        
        Args:
            window_size (int): Size of the sliding window for motion analysis
            frame_gap (int): Number of frames to skip between analysis
            n_cells (int): Number of cells to divide the field into
            line_of_scrimmage_region (float): Fraction of field height to focus on around LOS
        """
        self.motion_analyzer = MotionAnalyzer(
            window_size=window_size,
            frame_gap=frame_gap,
            n_cells=n_cells,
            line_of_scrimmage_region=line_of_scrimmage_region
        )
    
    def process_video(self, video_path):
        """
        Process a video file to detect the snap.
        
        Args:
            video_path (str): Path to the video file
            
        Returns:
            tuple: (snap_frame, vti, motion_diffs)
                snap_frame (int): Frame number where the snap was detected
                vti (ndarray): Vertical temporal image
                motion_diffs (ndarray): Motion difference values
        """
        # Mulder Get video dimensions
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        _, first_frame = cap.read()
        cap.release()
        if first_frame is None:
            raise ValueError("Could not read first frame")
            
        height = first_frame.shape[0]
        width = first_frame.shape[1]
        
        # Mulder Create default boundaries focusing on the center 50% of the frame
        n_points = 10
        x_points = np.linspace(0, width-1, n_points)
        y_points = np.linspace(0, height-1, n_points)
        
        # Mulder Focus on the center 50% of the frame
        center_start = int(height * 0.25)
        center_end = int(height * 0.75)
        boundaries_b1 = np.full(n_points, center_start, dtype=np.int32)
        boundaries_b2 = np.full(n_points, center_end, dtype=np.int32)
        
        # Mulder MotionAnalyzer returns snap_frame, vti, motion_diffs
        snap_frame, vti, motion_diffs = self.motion_analyzer.analyze_video(
            video_path, boundaries_b1, boundaries_b2
        )
        
        # Mulder Return all results for debugging/analysis
        return snap_frame, vti, motion_diffs