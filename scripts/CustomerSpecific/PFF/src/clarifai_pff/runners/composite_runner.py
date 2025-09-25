"""
Composite Runner for Complete Video Processing Pipeline

This module provides a composite service that orchestrates detection, tracking, and homography
runners to provide a complete video processing pipeline.
"""

from typing import List, Optional, Dict, Any
import logging

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types.data_types import Video, Frame as dtFrame
import clarifai.utils.logging as logging_utils
from clarifai_grpc.grpc.api.resources_pb2 import Frame
from google.protobuf.struct_pb2 import Struct

import clarifai_pff.utils.video as video_utils
from clarifai_pff.runners.detection_runner import DetectionRunner
from clarifai_pff.runners.tracking_runner import TrackingRunner
from clarifai_pff.runners.homography_runner import HomographyRunner

logger = logging_utils.get_logger(logging.INFO, name=__name__)


class CompositeRunner(ModelClass):
    """
    Composite runner that orchestrates detection, tracking, and homography runners.

    This runner combines the functionality of all individual runners to provide
    a complete video processing pipeline while maintaining the ability to use
    each component independently.
    """

    def __init__(self, folder: Optional[str] = None):
        super().__init__()
        self.folder = folder
        self.detection_runner: Optional[DetectionRunner] = None
        self.tracking_runner: Optional[TrackingRunner] = None
        self.homography_runner: Optional[HomographyRunner] = None

    def load_model(self):
        """Load all individual runners."""
        logger.info("Loading composite runner components...")

        # Initialize detection runner
        self.detection_runner = DetectionRunner(self.folder)
        self.detection_runner.load_model()

        # Initialize tracking runner
        self.tracking_runner = TrackingRunner(self.folder)
        self.tracking_runner.load_model()

        # Initialize homography runner
        self.homography_runner = HomographyRunner(self.folder)
        self.homography_runner.load_model()

        logger.info("All composite runner components loaded successfully")

    def _setup_video_stream(self, video: Video):
        """
        Setup video stream from video source.

        Args:
            video: Video object with bytes or URL

        Returns:
            Iterator over video frames

        Raises:
            ValueError: If video source is invalid
        """
        if not video.bytes and not video.url:
            raise ValueError("Video must have either bytes or url set.")

        if video.url:
            return video_utils.stream_frames_from_url(video.url, download_ok=True)
        elif video.bytes:
            from io import BytesIO
            bytes_io = BytesIO(video.bytes)

            import av
            return av.open(bytes_io).decode(video=0)
        else:
            raise ValueError("Video must have either bytes or url set.")

    def _setup_tracker(self, tracker_params: Optional[Dict[str, Any]] = None):
        """
        Setup tracking if parameters are provided.

        Args:
            tracker_params: Tracker configuration parameters

        Returns:
            Initialized tracker or None
        """
        if tracker_params is None:
            return None

        try:
            return self.tracking_runner._setup_tracker(tracker_params)
        except Exception as e:
            logger.error(f"Failed to setup tracker: {e}")
            return None

    def _create_combined_result(self, player_detections: List, homography_metadata: Struct) -> dtFrame:
        """
        Create combined result data structure.

        Args:
            player_detections: List of tracked player detections
            homography_metadata: Homography metadata

        Returns:
            Combined result data
        """
        result_data = Frame()

        # Add tracked player detections
        for region in player_detections:
            r = result_data.data.regions.add()
            r.CopyFrom(region.to_proto())

        # Add homography metadata
        result_data.data.metadata.CopyFrom(homography_metadata)

        return dtFrame(proto_frame=result_data)

    @ModelClass.method
    def predict(
        self,
        video: Video,
        tracker_params: dict = None,
        homography_params: dict = None,
        max_frames: int = None
    ) -> List[dtFrame]:
        """
        Process video using the complete pipeline (detection + tracking + homography).

        Args:
            video: Input video to process
            tracker_params: Optional parameters for multi-object tracking
            homography_params: Optional parameters for homography computation
            max_frames: Maximum number of frames to process (None for all frames)

        Returns:
            List of processed frame results with detections, tracking, and homography
        """
        results = []

        # Setup video stream
        stream = self._setup_video_stream(video)

        # Setup tracker if parameters provided
        tracker = self._setup_tracker(tracker_params)

        # Process each frame
        prev_frame = None
        prev_homography = None
        for frame_idx, frame in enumerate(stream):
            # Check frame limit
            if max_frames is not None and frame_idx >= max_frames:
                break

            logger.info(f"Processing frame {frame_idx}")

            try:
                # Step 1: Detect players and field elements
                player_detections, field_element_detections = self.detection_runner.detect_frame(frame)

                # Step 2: Track players (if tracker is available)
                if tracker is not None and player_detections:
                    player_detections = self.tracking_runner.track_frame(frame, player_detections, tracker)
            except Exception as e:
                logger.error(f"Error in detection/tracking for frame {frame_idx}: {e}")
                player_detections = []
                field_element_detections = []

            try:
                # Step 3: Compute homography
                homography_result = self.homography_runner.compute_homography(
                    frame, field_element_detections, homography_params=homography_params,
                    prev_frame=prev_frame, prev_homography=prev_homography
                )
                
                prev_frame = frame
                prev_homography = homography_result

                # Step 4: Create metadata
                homography_metadata = self.homography_runner._create_metadata(homography_result)
            except Exception as e:
                logger.error(f"Error in homography for frame {frame_idx}: {e}")
                homography_metadata = Struct()
                homography_metadata.update({'error': f"Homography failed: {str(e)}"})

            # Step 5: Create combined result
            result_data = self._create_combined_result([*player_detections, *field_element_detections], homography_metadata)
            results.append(result_data)

        logger.info(f"Processed {len(results)} frames")
        return results

    def run_detection_only(self, video: Video, max_frames: Optional[int] = None) -> List[dtFrame]:
        """
        Run only detection on the video.

        Args:
            video: Input video to process
            max_frames: Maximum number of frames to process

        Returns:
            List of detection results
        """
        return self.detection_runner.predict(video, max_frames=max_frames)

    def run_tracking_only(self, video: Video, tracker_params: Optional[Dict[str, Any]] = None,
                         max_frames: Optional[int] = None) -> List[dtFrame]:
        """
        Run only tracking on the video (requires detections).

        Args:
            video: Input video to process
            tracker_params: Optional tracker parameters
            max_frames: Maximum number of frames to process

        Returns:
            List of tracking results
        """
        return self.tracking_runner.predict(video, tracker_params, max_frames)

    def run_homography_only(self, video: Video, field_element_detections: List[List],
                           homography_params: Optional[Dict[str, Any]] = None,
                           max_frames: Optional[int] = None) -> List[dtFrame]:
        """
        Run only homography on the video (requires field element detections).

        Args:
            video: Input video to process
            field_element_detections: List of field element detections per frame
            homography_params: Optional homography parameters
            max_frames: Maximum number of frames to process

        Returns:
            List of homography results
        """
        return self.homography_runner.predict(video, field_element_detections, homography_params, max_frames)