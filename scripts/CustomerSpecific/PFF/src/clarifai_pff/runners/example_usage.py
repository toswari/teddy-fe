"""
Example Usage of Modular Video Processing Runners

This script demonstrates how to use the individual runners independently
or compose them together for complete video processing pipelines.
"""

import os
from typing import List, Optional, Dict, Any

from clarifai.runners.utils.data_types.data_types import Video, Frame as dtFrame

# Import individual runners
from clarifai_pff.runners.detection_runner import DetectionRunner
from clarifai_pff.runners.tracking_runner import TrackingRunner
from clarifai_pff.runners.homography_runner import HomographyRunner

# Import composite runner
from clarifai_pff.runners.composite_runner import CompositeRunner


def example_detection_only():
    """Example: Run only detection on a video."""
    print("=== Detection Only Example ===")

    # Initialize detection runner
    detection_runner = DetectionRunner()
    detection_runner.load_model()

    # Create a video object (replace with actual video)
    video_path = "file_path"
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)
    # video = Video(url="file_path")

    # Run detection
    results = detection_runner.predict(video, max_frames=10)
    print(f"Detection completed. Processed {len(results)} frames.")
    return results


def example_tracking_only():
    """Example: Run only tracking on a video."""
    print("=== Tracking Only Example ===")

    # Initialize tracking runner
    tracking_runner = TrackingRunner()
    tracking_runner.load_model()

    # Create a video object (replace with actual video)
    # Create a video object (replace with actual video)
    video_path = "file_path"
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)
    # Configure tracker parameters
    tracker_params = {
        "max_dead": 100,
        "max_emb_distance": 0.0,
        "var_tracker": "manorm",
        "initialization_confidence": 0.85,
        "min_confidence": 0.51,
        "association_confidence": [0.39],
        "min_visible_frames": 0,
        "covariance_error": 100,
        "observation_error": 10,
        "max_distance": [0.5],
        "max_disappeared": 8,
        "distance_metric": "diou",
        "track_aiid": ["players"],
        "track_id_prefix": "0",
        "use_detect_box": 0,
        "project_track": 0,
        "project_fix_box_size": 0,
        "detect_box_fall_back": 0
    }
    player_detections = []  # Placeholder for player detections per frame
    # Run tracking
    results = tracking_runner.predict(video, player_detections, tracker_params, max_frames=10)

    print(f"Tracking completed. Processed {len(results)} frames.")
    return results


def example_homography_only():
    """Example: Run only homography on a video."""
    print("=== Homography Only Example ===")

    # Initialize homography runner
    homography_runner = HomographyRunner()
    homography_runner.load_model()

    # Optionally set custom field info (e.g., for different leagues)
    # homography_runner.set_field_info(FIELD_INFOS[League.NFL])  # Default
    # homography_runner.set_field_info(FIELD_INFOS[League.SOCCER])  # For soccer

    # Create a video object (replace with actual video)
    video_path = "file_path"
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)
    # Note: In practice, you would need field element detections from a detection runner
    # This is a placeholder - you would get this from DetectionRunner
    field_element_detections = []  # Placeholder for field element detections

    # Configure homography parameters (field_info will be preserved from default config)
    homography_params = {
        'transforms': [
            dict(name='mean_blur_2d', kernel_size=3),
            dict(name='cvtGray'),
            dict(name='gaussian_adaptive_threshold', block_size=129, c=-16),
            dict(name='canny_edge', low_threshold=50, high_threshold=150),
            dict(name='hough_lines_xyxy', rho=1, theta=3.14159/180, threshold=150),
        ],
        'directional_threshold': 0.995
        # Note: field_info is automatically included from default configuration
    }

    # Run homography
    results = homography_runner.predict(video, field_element_detections, homography_params, max_frames=10)

    print(f"Homography completed. Processed {len(results)} frames.")
    return results


def example_composite_pipeline():
    """Example: Run the complete pipeline using the composite runner."""
    print("=== Composite Pipeline Example ===")

    # Initialize composite runner
    composite_runner = CompositeRunner()
    composite_runner.load_model()

    # Create a video object (replace with actual video)
    # Create a video object (replace with actual video)
    video_path = "file_path"
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)
    # Configure parameters
    tracker_params = {
        "max_dead": 100,
        "max_emb_distance": 0.0,
        "var_tracker": "manorm",
        "initialization_confidence": 0.85,
        "min_confidence": 0.51,
        "association_confidence": [0.39],
        "min_visible_frames": 0,
        "covariance_error": 100,
        "observation_error": 10,
        "max_distance": [0.5],
        "max_disappeared": 8,
        "distance_metric": "diou",
        "track_aiid": ["players"],
        "track_id_prefix": "0",
        "use_detect_box": 0,
        "project_track": 0,
        "project_fix_box_size": 0,
        "detect_box_fall_back": 0
    }

    homography_params = {
        'transforms': [
            dict(name='mean_blur_2d', kernel_size=3),
            dict(name='cvtGray'),
            dict(name='gaussian_adaptive_threshold', block_size=129, c=-16),
            dict(name='canny_edge', low_threshold=50, high_threshold=150),
            dict(name='hough_lines_xyxy', rho=1, theta=3.14159/180, threshold=150),
        ],
        'directional_threshold': 0.995
    }

    # Run complete pipeline
    results = composite_runner.predict(
        video,
        tracker_params=tracker_params,
        max_frames=5
    )
    print(f"Complete pipeline completed. Processed {len(results)} frames.")
    return results


def example_custom_composition():
    """Example: Compose runners manually for custom workflows."""
    print("=== Custom Composition Example ===")

    # Initialize individual runners
    detection_runner = DetectionRunner()
    detection_runner.load_model()

    tracking_runner = TrackingRunner()
    tracking_runner.load_model()

    homography_runner = HomographyRunner()
    homography_runner.load_model()

    # Create a video object (replace with actual video)
    # Create a video object (replace with actual video)
    video_path = "file_path"
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)
    # Step 1: Run detection
    detection_results = detection_runner.predict(video, max_frames=5)
    print(f"Detection completed. Processed {len(detection_results)} frames.")

    # Step 2: Extract detections for tracking and homography
    # (In practice, you would extract the detections from detection_results)

    # Step 3: Run tracking with custom parameters
    tracker_params = {
        "max_dead": 100,
        "max_emb_distance": 0.0,
        "var_tracker": "manorm",
        "initialization_confidence": 0.85,
        "min_confidence": 0.51,
        "association_confidence": [0.39],
        "min_visible_frames": 0,
        "covariance_error": 100,
        "observation_error": 10,
        "max_distance": [0.5],
        "max_disappeared": 8,
        "distance_metric": "diou",
        "track_aiid": ["players"],
        "track_id_prefix": "0",
        "use_detect_box": 0,
        "project_track": 0,
        "project_fix_box_size": 0,
        "detect_box_fall_back": 0
    }
    tracking_results = tracking_runner.predict(video, detection_results,tracker_params, max_frames=5)
    print(f"Tracking completed. Processed {len(tracking_results)} frames.")

    # Step 4: Run homography with custom parameters
    homography_params = {
        'transforms': [
            dict(name='mean_blur_2d', kernel_size=3),
            dict(name='cvtGray'),
            dict(name='gaussian_adaptive_threshold', block_size=129, c=-16),
            dict(name='canny_edge', low_threshold=50, high_threshold=150),
            dict(name='hough_lines_xyxy', rho=1, theta=3.14159/180, threshold=150),
        ],
        'directional_threshold': 0.995
    }

    homography_results = homography_runner.predict(video, field_element_detections, homography_params, max_frames=5)
    print(f"Homography completed. Processed {len(homography_results)} frames.")

    return detection_results, tracking_results, homography_results


def example_field_info_configuration():
    """Example: Demonstrate different field info configurations."""
    print("=== Field Info Configuration Example ===")

    from clarifai_pff.auto_homography import FIELD_INFOS, League

    # Initialize homography runner
    homography_runner = HomographyRunner()
    homography_runner.load_model()

    # Show current field info
    current_field_info = homography_runner.get_field_info()
    print(f"Current field info: {type(current_field_info).__name__}")

    # Set different field info for different sports
    try:
        # For NFL
        homography_runner.set_field_info(FIELD_INFOS[League.NFL])
        print("Set field info to NFL configuration")

        # For Soccer (if available)
        # homography_runner.set_field_info(FIELD_INFOS[League.SOCCER])
        # print("Set field info to Soccer configuration")

    except Exception as e:
        print(f"Error setting field info: {e}")


def example_error_handling():
    """Example: Demonstrate error handling in runners."""
    print("=== Error Handling Example ===")

    try:
        # Initialize runner with non-existent model folder
        detection_runner = DetectionRunner(folder="/non/existent/path")
        detection_runner.load_model()
    except Exception as e:
        print(f"Expected error when loading from non-existent path: {e}")

    try:
        # Initialize runner with valid path
        detection_runner = DetectionRunner()
        detection_runner.load_model()

        # Try to process with invalid video
        invalid_video = Video()  # No bytes or URL
        results = detection_runner.predict(invalid_video)
    except ValueError as e:
        print(f"Expected error with invalid video: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

    try:
        # Test homography with missing field info
        homography_runner = HomographyRunner()
        # Don't call load_model() to simulate missing field info
        homography_runner.config = None
        # This should raise an error
        homography_runner.compute_homography(None, [])
    except Exception as e:
        print(f"Expected error with missing field info: {e}")


if __name__ == "__main__":
    """Run examples when script is executed directly."""

    print("Video Processing Runners - Example Usage")
    print("=" * 50)

    # Note: These examples require actual video files and model files
    # Uncomment the examples you want to run

    # example_detection_only()
    # example_tracking_only()
    # example_homography_only()
    # example_composite_pipeline()
    # example_custom_composition()
    # example_field_info_configuration()
    # example_error_handling()

    # print("\nExamples completed. Check the code comments for usage details.")
    # print("Remember to:")
    # print("1. Replace '/Users/sanjay/work/PS-Field-Engineering/scripts/CustomerSpecific/PFF/samples/5069060_257_SL.mp4' with actual video paths")
    # print("2. Ensure model files are available in the expected locations")
    # print("3. Handle errors appropriately in production code")