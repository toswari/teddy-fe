#!/usr/bin/env python3
"""
Football Snap Detection CLI Tool

Analyzes football game videos to detect the moment of snap using computer vision,
Clarifai detection and motion analysis.
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(
        description='Football Snap Detection CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py video.mp4
  python main.py video.mp4 --output ./results
  python main.py sample_videos/Sample_Video_1.mp4 --gif-window 45
        """
    )
    
    parser.add_argument('video', help='Path to the input video file')
    parser.add_argument('--output', '-o', default='outputs', 
                        help='Output directory for results (default: outputs)')
    parser.add_argument('--gif-window', type=int, default=30,
                        help='Number of frames before/after snap for GIF (default: 30)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--debug-clarifai', action='store_true',
                        help='Print detailed Clarifai prediction structure for early frames')
    parser.add_argument('--no-cache', action='store_true',
                        help='Disable detection caching for this run')
    parser.add_argument('--cache-dir', default='cache',
                        help='Directory to store/load detection caches (default: cache)')
    parser.add_argument('--min-los-cluster-size', type=int, default=10,
                        help='Minimum total players required in LOS cluster before snap considered (default: 10)')
    parser.add_argument('--min-active-los-players', type=int, default=3,
                        help='Minimum LOS players showing motion to validate snap onset (default: 3)')
    
    args = parser.parse_args()
    
    # Validate input video file
    if not os.path.isfile(args.video):
        print(f"Error: Video file '{args.video}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Check file format
    valid_extensions = ('.mp4', '.avi', '.mov')
    if not args.video.lower().endswith(valid_extensions):
        print(f"Error: Invalid file format. Supported formats: {valid_extensions}", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Load .env if present
    load_dotenv(dotenv_path=Path('.env'))

    # Initialize detector (import here to avoid loading heavy dependencies for --help)
    if args.verbose:
        print("Initializing Clarifai model (CLARIFAI_PAT from environment/.env)...")
    try:
        from snap_detector import SnapDetector
        model_url = os.getenv('CLARIFAI_MODEL_URL', 'https://clarifai.com/pff-org/labelstudio-unified/models/unified-model')
        detector = SnapDetector(
            clarifai_model_url=model_url,
            debug_clarifai=args.debug_clarifai,
            enable_detection_cache=not args.no_cache,
            detection_cache_dir=args.cache_dir,
            min_los_cluster_size=args.min_los_cluster_size,
            min_active_los_players=args.min_active_los_players,
            verbose=args.verbose,
        )
    except ImportError as e:
        print(f"Error: Required dependencies not installed. Please run: pip install -r requirements.txt", file=sys.stderr)
        print(f"Import error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generate output file paths
    video_name = Path(args.video).stem
    graph_path = os.path.join(args.output, f'{video_name}_motion.png')
    
    print(f"Processing video: {args.video}")
    print(f"Output directory: {args.output}")
    
    try:
        # Create a mock processing status for compatibility with existing code
        task_id = "cli_task"
        processing_status = {task_id: {'status': 'Starting...', 'progress': 0}}
        
        # Detect snaps
        if args.verbose:
            print("Analyzing video for snap detection...")
        
        snap_frames, motion_history, camera_motion_history, los_velocities_history = detector.detect_snap(
            args.video, task_id, processing_status
        )

        # Plot LOS velocities for visual inspection
        los_velocities_plot_path = os.path.join(args.output, f'{video_name}_los_velocities.png')
        detector.plot_los_velocities(los_velocities_history, los_velocities_plot_path)
        print(f"LOS velocities plot created: {los_velocities_plot_path}")
        
        if not snap_frames:
            print("Warning: No snap moments detected in the video.")
        else:
            print(f"Detected {len(snap_frames)} snap(s) at frame(s): {', '.join(map(str, snap_frames))}")
        
        # Create GIFs for each snap
        if snap_frames:
            if args.verbose:
                print("Creating snap GIFs...")
            
            created_gifs = detector.create_snap_gifs(
                args.video, snap_frames, args.output, video_name, args.gif_window
            )
            
            for gif_path in created_gifs:
                print(f"GIF created: {gif_path}")
        
        # Create motion graph
        if args.verbose:
            print("Creating motion analysis graph...")
        
        detector.plot_motion_graph(graph_path, motion_history, camera_motion_history, snap_frames)
        print(f"Motion graph created: {graph_path}")
        
        print("\nProcessing complete!")
        
    except Exception as e:
        import traceback
        print(f"Error processing video: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()