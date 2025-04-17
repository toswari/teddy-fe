"""
Motion analysis module for detecting the moment of snap.
Implements the Variable Threshold Image (VTI) approach with focus on line of scrimmage.
"""

import numpy as np
import cv2
from scipy.signal import find_peaks

class MotionAnalyzer:
    def __init__(self, window_size=100, frame_gap=2, n_cells=10, line_of_scrimmage_region=0.2):
        """
        Initialize the motion analyzer.
        
        Args:
            window_size (int): Size of the sliding window for analysis
            frame_gap (int): Gap between frames for optical flow calculation
            n_cells (int): Number of cells to divide the field into
            line_of_scrimmage_region (float): Fraction of field height to focus on around the line of scrimmage
        """
        self.window_size = window_size
        self.frame_gap = frame_gap
        self.n_cells = n_cells
        self.line_of_scrimmage_region = line_of_scrimmage_region
        
    def compute_optical_flow(self, prev_frame, curr_frame):
        """
        Compute dense optical flow between two frames.
        
        Args:
            prev_frame (numpy.ndarray): Previous frame
            curr_frame (numpy.ndarray): Current frame
            
        Returns:
            numpy.ndarray: Optical flow field
        """
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        
        # Mulder Compute optical flow using Farneback method
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        
        return flow
    
    def estimate_camera_motion(self, flow, top_boundary, bottom_boundary):
        """
        Estimate camera motion using the yard lines region.
        
        Args:
            flow (numpy.ndarray): Optical flow field
            top_boundary (numpy.ndarray): Top boundary of the field (Y-coords)
            bottom_boundary (numpy.ndarray): Bottom boundary of the field (Y-coords)
            
        Returns:
            tuple: (camera_motion_y, camera_motion_x)
        """
        height, width = flow.shape[:2]
        
        # Mulder Create mask for yard line region
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # Mulder Convert boundaries to integers
        top_y = int(top_boundary[0])
        bottom_y = int(bottom_boundary[0])
        
        # Mulder Define yard line region (exclude the line of scrimmage area)
        los_center = (top_y + bottom_y) // 2
        los_margin = int((bottom_y - top_y) * self.line_of_scrimmage_region / 2)
        
        # Mulder Fill in two regions: above and below LOS
        mask[top_y:los_center-los_margin, :] = 255  # Mulder Upper field region
        mask[los_center+los_margin:bottom_y, :] = 255  # Mulder Lower field region
        
        # Mulder Calculate mean flow in masked regions
        masked_flow_y = np.ma.array(flow[..., 1], mask=(mask == 0))
        masked_flow_x = np.ma.array(flow[..., 0], mask=(mask == 0))
        
        camera_motion_y = np.ma.median(masked_flow_y)
        camera_motion_x = np.ma.median(masked_flow_x)
        
        return float(camera_motion_y), float(camera_motion_x)
    
    def compute_vti(self, video_frames, top_boundary, bottom_boundary):
        """
        Compute the Variable Threshold Image (VTI) for a sequence of frames,
        focusing on player motion by removing camera motion.
        
        Args:
            video_frames (list): List of video frames
            top_boundary (numpy.ndarray): Top boundary of the field (Y-coords)
            bottom_boundary (numpy.ndarray): Bottom boundary of the field (Y-coords)
            
        Returns:
            numpy.ndarray: Variable Threshold Image
        """
        n_frames = len(video_frames)
        if n_frames < self.frame_gap:
             return np.zeros((self.n_cells, n_frames))
             
        vti = np.zeros((self.n_cells, n_frames))
        
        # Mulder Ensure boundaries are valid
        top_y = int(top_boundary[0])
        bottom_y = int(bottom_boundary[0])
        if top_y >= bottom_y:
            print(f"Warning: Invalid boundaries top_y={top_y}, bottom_y={bottom_y}")
            return vti
            
        field_height = bottom_y - top_y
        # Mulder Calculate LOS region
        los_center_y = top_y + field_height * 0.5
        los_region_height = field_height * self.line_of_scrimmage_region
        los_start = int(los_center_y - los_region_height / 2)
        los_end = int(los_center_y + los_region_height / 2)
        
        # Mulder Clamp LOS region to frame boundaries
        frame_height = video_frames[0].shape[0]
        los_start = max(0, los_start)
        los_end = min(frame_height, los_end)
        
        for i in range(0, n_frames - self.frame_gap, self.frame_gap):
            prev_frame = video_frames[i]
            curr_frame = video_frames[i + self.frame_gap]
            
            # Mulder Compute overall flow
            flow = self.compute_optical_flow(prev_frame, curr_frame)
            
            # Mulder Estimate camera motion using yard lines
            camera_y, camera_x = self.estimate_camera_motion(flow, top_boundary, bottom_boundary)
            
            # Mulder Remove camera motion from flow
            flow_y = flow[..., 1] - camera_y
            flow_x = flow[..., 0] - camera_x
            
            # Mulder Compute motion magnitude after camera correction
            magnitude = np.sqrt(flow_x**2 + flow_y**2)
            
            # Mulder Focus on LOS region
            los_magnitude = magnitude[los_start:los_end, :]
            if los_magnitude.shape[0] == 0:
                continue
                
            # Mulder Divide into cells and compute mean motion
            cell_height = los_magnitude.shape[0] // self.n_cells
            if cell_height <= 0:
                continue
                
            for cell in range(self.n_cells):
                start = cell * cell_height
                end = min(start + cell_height, los_magnitude.shape[0])
                if start >= end:
                    continue
                cell_magnitude = los_magnitude[start:end, :]
                if cell_magnitude.size == 0:
                    vti[cell, i] = 0.0
                else:
                    mean_val = np.nanmean(cell_magnitude)
                    vti[cell, i] = 0.0 if np.isnan(mean_val) else mean_val
                    
        return vti
    
    def detect_snap_moment(self, vti):
        """
        Detect the moment of snap by working backwards from the first major motion peak
        to find where the initial movement started. The approach:
        1. Find the first significant peak of motion
        2. Work backwards to find where the motion first started increasing from rest
        
        Args:
            vti (numpy.ndarray): Variable Threshold Image
            
        Returns:
            tuple: (snap_frame_index, motion_diffs_array)
        """
        n_frames = vti.shape[1]
        motion_diffs = np.zeros(n_frames)
        if n_frames <= 2 * self.window_size:
             print("Warning: Not enough frames for windowed motion difference calculation.")
             return 0, motion_diffs 
             
        # Mulder Calculate motion differences
        window_size_motion = 30  # Mulder Smaller window for more sensitivity
        for i in range(window_size_motion, n_frames - window_size_motion):
            before_slice = vti[:, max(0, i-window_size_motion):i]
            after_slice = vti[:, i:min(n_frames, i+window_size_motion)]
            
            before_mean = np.nanmean(before_slice) if before_slice.size > 0 else 0.0
            after_mean = np.nanmean(after_slice) if after_slice.size > 0 else 0.0
            
            before_mean = 0.0 if np.isnan(before_mean) else before_mean
            after_mean = 0.0 if np.isnan(after_mean) else after_mean
            
            motion_diffs[i] = after_mean - before_mean

        # Mulder Apply minimal smoothing
        window_size = 3
        kernel = np.ones(window_size) / window_size
        smoothed_diffs = np.convolve(motion_diffs, kernel, mode='same')
        
        # Mulder Find the first major peak in the first half of the video
        search_range = int(n_frames * 0.5)  # Mulder Look in first half
        peak_threshold = 0.2  # Mulder Threshold for significant motion
        
        # Mulder Find the first peak that exceeds our threshold
        peak_frame = 0
        for i in range(window_size_motion, search_range):
            if smoothed_diffs[i] > peak_threshold:
                peak_frame = i
                print(f"Found first major motion peak at frame {peak_frame}")
                break
                
        if peak_frame == 0:
            print("No significant peak found")
            return 0, motion_diffs
            
        # Mulder Work backwards from the peak to find where motion first started
        motion_threshold = 0.02  # Mulder Very small threshold to detect initial movement
        window_size_check = 10  # Mulder Window to check for consistent low motion
        
        for i in range(peak_frame - 1, window_size_motion, -1):
            # Mulder Check if we're at a point of very low motion
            current_window = smoothed_diffs[i-window_size_check:i]
            next_window = smoothed_diffs[i:i+window_size_check]
            
            # Mulder If current window is low motion and next window shows increase
            if (np.all(np.abs(current_window) < motion_threshold) and 
                np.mean(next_window) > motion_threshold):
                snap_frame = i
                print(f"Found snap initiation at frame {snap_frame}")
                return snap_frame, motion_diffs
        
        # Mulder Fallback: if no clear initiation point found, go back a fixed amount from peak
        snap_frame = max(window_size_motion, peak_frame - 30)
        print(f"No clear initiation point found, using frame {snap_frame}")
        
        return snap_frame, motion_diffs
    
    def analyze_video(self, video_path, top_boundary, bottom_boundary):
        """
        Analyze a video file to detect the snap moment.
        
        Args:
            video_path (str): Path to the video file
            top_boundary (numpy.ndarray): Top boundary of the field
            bottom_boundary (numpy.ndarray): Bottom boundary of the field
            
        Returns:
            tuple: (snap_frame, vti, motion_diffs)
        """
        # Mulder Open the video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
            
        # Mulder Read frames into memory
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        
        if not frames:
            raise ValueError("No frames were read from the video")
            
        # Mulder Compute VTI
        vti = self.compute_vti(frames, top_boundary, bottom_boundary)
        
        # Mulder Detect snap moment and get motion differences
        snap_frame, motion_diffs = self.detect_snap_moment(vti)
        
        # Mulder Return all results
        return snap_frame, vti, motion_diffs 