"""
Demo script for testing the snap detection package.
"""

import cv2
import numpy as np
import traceback
import os
from snap_detection import SnapDetector, save_analysis_results

def main():
    # Initialize the detector
    detector = SnapDetector(
        window_size=50, 
        frame_gap=2,
        n_cells=10,
        line_of_scrimmage_region=0.4 
    )
    
    # Process the sample video
    video_path = "customer_data/videos/58203_003141_Sideline.mp4"
    output_dir = "output_frames"
    cap = None
    
    try:
        print(f"Processing video: {video_path}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"Output will be saved to: {os.path.abspath(output_dir)}")
        
        # Get video properties
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"Video properties: {fps:.2f} FPS, {total_frames} total frames\n")
        cap.release()

        # Process Video for Snap
        print("Processing video for snap detection...")
        snap_frame, vti, motion_diffs = detector.process_video(video_path) 
        print(f"Detected snap at frame: {snap_frame} ({(snap_frame/fps):.2f}s)")
        
        # Save Analysis Results
        print("\nSaving analysis results...")
        save_analysis_results(
            video_path, 
            output_dir, 
            snap_frame, 
            vti, 
            motion_diffs,
            save_frames=True,
            save_gif=True,
            gif_fps=10,
            frames_before_snap=5,
            frames_after_snap=5
        )
                
    except Exception as e:
        print(f"\nError during processing: {str(e)}")
        traceback.print_exc()
    finally:
        if cap is not None:
            cap.release()
        print("\nDemo finished.")

if __name__ == "__main__":
    main() 