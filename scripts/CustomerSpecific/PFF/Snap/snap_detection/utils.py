"""
Utility functions for saving and visualizing snap detection results.
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import imageio

def save_motion_diffs_plot(motion_diffs, snap_frame, output_dir):
    """Save a plot of motion differences over time with the detected snap point."""
    plt.figure(figsize=(12, 6))
    plt.plot(motion_diffs, 'b-')
    if snap_frame is not None:
        plt.axvline(x=snap_frame, color='r', linestyle='--', label='Detected Snap')
    plt.title('Motion Differences Over Time')
    plt.xlabel('Frame Number')
    plt.ylabel('Motion Difference')
    plt.legend()
    plt.grid(True)
    plot_path = os.path.join(output_dir, 'motion_differences_plot.png')
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    return plot_path

def create_snap_sequence_gif(video_path, output_path, snap_frame, frames_before=5, frames_after=5, fps=10):
    """Create a GIF of the sequence around the snap moment."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = max(0, snap_frame - frames_before)
    end_frame = min(total_frames - 1, snap_frame + frames_after)
    
    frames = []
    frame_num = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_num >= start_frame and frame_num <= end_frame:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
            
        if frame_num > end_frame:
            break
            
        frame_num += 1
    
    cap.release()
    imageio.mimsave(output_path, frames, fps=fps, loop=0)
    return output_path

def save_analysis_results(video_path, output_dir, snap_frame, vti, motion_diffs, **kwargs):
    """Save all analysis results including VTI heatmap, motion differences, and frame sequence."""
    os.makedirs(output_dir, exist_ok=True)
    output_files = []
    
    # Mulder Save VTI heatmap
    if vti is not None and vti.size > 0:
        vti_path = os.path.join(output_dir, "vti_heatmap.png")
        vti_normalized = cv2.normalize(vti, None, 0, 255, cv2.NORM_MINMAX)
        vti_image = vti_normalized.astype(np.uint8)
        vti_image_resized = cv2.resize(vti_image, (vti.shape[1], vti.shape[0]*20), 
                                     interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(vti_path, vti_image_resized)
        output_files.append(vti_path)
    
    # Mulder Save motion differences data and plot
    if motion_diffs is not None and motion_diffs.size > 0:
        diffs_path = os.path.join(output_dir, "motion_diffs.txt")
        np.savetxt(diffs_path, motion_diffs, fmt='%.4f')
        output_files.append(diffs_path)
        
        plot_path = save_motion_diffs_plot(motion_diffs, snap_frame, output_dir)
        output_files.append(plot_path)
    
    # Mulder Save frames if requested
    if kwargs.get('save_frames', True):
        frames_dir = os.path.join(output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        start_frame = max(0, snap_frame - kwargs.get('frames_before_snap', 5))
        end_frame = min(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1, 
                       snap_frame + kwargs.get('frames_after_snap', 5))
        
        frame_num = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_num >= start_frame and frame_num <= end_frame:
                cv2.putText(frame, f"Frame: {frame_num} ({frame_num/fps:.2f}s)", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                frame_path = os.path.join(frames_dir, f"frame_{frame_num:04d}.png")
                cv2.imwrite(frame_path, frame)
                output_files.append(frame_path)
            
            if frame_num > end_frame:
                break
                
            frame_num += 1
        
        cap.release()
    
    # Mulder Create GIF if requested
    if kwargs.get('save_gif', True):
        gif_path = os.path.join(output_dir, "snap_sequence.gif")
        gif_path = create_snap_sequence_gif(
            video_path, gif_path, snap_frame,
            frames_before=kwargs.get('frames_before_snap', 5),
            frames_after=kwargs.get('frames_after_snap', 5),
            fps=kwargs.get('gif_fps', 10)
        )
        output_files.append(gif_path)
    
    return output_files 