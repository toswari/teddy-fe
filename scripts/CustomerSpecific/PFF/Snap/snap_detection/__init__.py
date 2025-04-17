"""
Snap Detection Module
"""

from .snap_detector import SnapDetector
from .utils import save_analysis_results

__version__ = "0.1.0"

def process_video(video_path, output_dir=None, **kwargs):
    """Process a video file to detect the snap moment and optionally save analysis results."""
    detector = SnapDetector(
        window_size=kwargs.get('window_size', 50),
        frame_gap=kwargs.get('frame_gap', 2),
        n_cells=kwargs.get('n_cells', 10),
        line_of_scrimmage_region=kwargs.get('line_of_scrimmage_region', 0.4)
    )
    
    snap_frame, vti, motion_diffs = detector.process_video(video_path)
    
    import cv2
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    
    snap_time = snap_frame / fps
    results = {
        'vti': vti,
        'motion_diffs': motion_diffs,
        'output_files': []
    }
    
    if output_dir:
        save_params = {
            'save_frames': kwargs.get('save_frames', True),
            'save_gif': kwargs.get('save_gif', True),
            'gif_fps': kwargs.get('gif_fps', 10),
            'frames_before_snap': kwargs.get('frames_before_snap', 5),
            'frames_after_snap': kwargs.get('frames_after_snap', 5)
        }
        results['output_files'] = save_analysis_results(
            video_path, output_dir, snap_frame, vti, motion_diffs, **save_params
        )
    
    return snap_frame, snap_time, results
