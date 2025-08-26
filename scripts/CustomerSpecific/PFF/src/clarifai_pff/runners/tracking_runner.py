"""
Tracking Runner for Player Re-identification and Multi-Object Tracking

This module provides a standalone tracking service that can be deployed independently
or composed with other runners for complete video processing pipelines.
"""

from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging
from time import perf_counter_ns
from contextlib import contextmanager

import onnx
import onnxruntime as ort
import os
import cv2
import numpy as np

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types.data_types import Video, Region, Concept, Frame as dtFrame
import clarifai.utils.logging as logging_utils
from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data, Region as cfRegion
from google.protobuf.struct_pb2 import Struct

from clarifai_pff.tracking.reid import KalmanREID
from clarifai_pff.utils.transforms import letterbox
import clarifai_pff.utils.video as video_utils

logger = logging_utils.get_logger(logging.INFO, name=__name__)


@dataclass
class TrackingConfig:
    """Configuration for tracking and re-identification."""
    model_folder: str
    reid_model_path: Optional[str] = None
    max_disappeared: int = 30
    max_distance: float = 50.0
    min_confidence: float = 0.3
    embedding_threshold: float = 0.7

    def __post_init__(self):
        if self.reid_model_path is None:
            self.reid_model_path = os.path.join(self.model_folder, '1', 'reid.skl')


@contextmanager
def timing_context(operation_name: str):
    """Context manager for timing operations."""
    start_time = perf_counter_ns()
    try:
        yield
    finally:
        end_time = perf_counter_ns()
        duration_seconds = (end_time - start_time) / 1e9
        logger.info(f"{operation_name} took {duration_seconds:.3f} s")


class TrackingRunner(ModelClass):
    """
    Standalone tracking runner for player re-identification and multi-object tracking.

    This runner can be deployed independently or composed with other runners
    for complete video processing pipelines.
    """

    def __init__(self, folder: Optional[str] = None):
        super().__init__()
        self.folder = folder
        self.config: Optional[TrackingConfig] = None
        self.embedder_session: Optional[ort.InferenceSession] = None
        self.embedder_input_shape: Optional[Tuple[int, int]] = None
        self.tracker: Optional[KalmanREID] = None

    def _get_model_folder(self) -> str:
        """Get the model folder path."""
        return getattr(self, 'folder', False) or os.path.dirname(os.path.dirname(__file__))

    def _load_embedder_model(self, model_path: str) -> Tuple[ort.InferenceSession, Tuple[int, int]]:
        """
        Load the embedding model for re-identification.

        Args:
            model_path: Path to the embedding model file

        Returns:
            Tuple of (session, input_shape)

        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If model loading fails
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Embedder model file not found: {model_path}")

        logger.info(f"Loading embedder model from {model_path}")

        try:
            # Load model to get input dimensions
            model = onnx.load(model_path)
            input_dims = [x.dim_value for x in model.graph.input[0].type.tensor_type.shape.dim[-2:]]
            input_shape = tuple(input_dims[::-1])  # Convert from (height, width) to (width, height)

            # Create inference session
            session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])

            logger.info(f"Embedder model loaded with input shape: {input_shape}")
            return session, input_shape

        except Exception as e:
            raise RuntimeError(f"Failed to load embedder model: {e}")

    def load_model(self):
        """Load the embedding model and initialize tracking configuration."""
        model_folder = self._get_model_folder()
        embedder_path = os.path.join(model_folder, '1', 'embedder.onnx')

        self.embedder_session, self.embedder_input_shape = self._load_embedder_model(embedder_path)
        self.config = TrackingConfig(model_folder)

        logger.info("Tracking model loaded successfully")

    def _extract_player_crops(self, frame, detections: List[Region]) -> np.ndarray:
        """
        Extract cropped regions for detected players.

        Args:
            frame: Input frame
            detections: List of player detections

        Returns:
            Array of cropped player images
        """
        frame_array = frame.to_ndarray(format="rgb24")
        frame_size = frame_array.shape[:2][::-1]  # (width, height)

        crops = []
        for region in detections:
            # Convert normalized coordinates to pixel coordinates
            x, y, xx, yy = [coord * size for coord, size in zip(region.box, [*frame_size] * 2)]

            # Extract crop
            crop = frame_array[int(y):int(yy), int(x):int(xx)]

            # Resize to embedding model input size
            crop = cv2.resize(crop, self.embedder_input_shape)

            # Convert to CHW format and normalize
            crop = np.moveaxis(crop, -1, 0)  # HWC to CHW
            crop = crop / 255.0

            crops.append(crop)

        return np.array(crops).astype(np.float32)

    def _compute_embeddings(self, crops: np.ndarray) -> np.ndarray:
        """
        Compute embeddings for player crops.

        Args:
            crops: Array of cropped player images

        Returns:
            Array of embeddings
        """
        if len(crops) == 0:
            return np.array([])

        with timing_context("Embedding computation"):
            embeddings = self.embedder_session.run(
                None, {self.embedder_session.get_inputs()[0].name: crops}
            )[0]

        logger.info(f"Embeddings shape: {embeddings.shape}")
        return embeddings

    def _add_embeddings_to_detections(self, detections: List[Region], embeddings: np.ndarray):
        """
        Add computed embeddings to detection regions.

        Args:
            detections: List of detections
            embeddings: Computed embeddings
        """
        for region, embedding in zip(detections, embeddings):
            emb = region.proto.data.embeddings.add()
            emb.vector.extend(embedding.tolist())

    def _setup_tracker(self, tracker_params: Optional[Dict[str, Any]] = None) -> KalmanREID:
        """
        Setup the multi-object tracker.

        Args:
            tracker_params: Optional tracker parameters

        Returns:
            Initialized tracker

        Raises:
            RuntimeError: If tracker setup fails
        """
        if tracker_params is None:
            return None

        try:
            # Add reid model path to tracker params
            reid_model_path = os.path.join(self._get_model_folder(), '1', 'reid.skl')
            if not os.path.exists(reid_model_path):
                logger.warning(f"ReID model not found at {reid_model_path}, skipping tracking")
                return None

            tracker_params["reid_model_path"] = reid_model_path

            # Initialize tracker
            tracker = KalmanREID(**tracker_params)
            tracker.init_state()
            return tracker

        except Exception as e:
            logger.error(f"Failed to setup tracker: {e}")
            return None

    def _apply_tracking(self, detections: List[Region], tracker: KalmanREID) -> List[Region]:
        """
        Apply multi-object tracking to detections.

        Args:
            detections: List of detections
            tracker: Initialized tracker instance

        Returns:
            List of tracked regions
        """
        # Create frame for tracker
        cf_frame = Frame()
        for region in detections:
            r = cf_frame.data.regions.add()
            r.CopyFrom(region.to_proto())
            r.value = region.concepts[0].value  # Tracker expects this

        # Run tracker
        tracker(cf_frame.data)

        # Convert back to Region objects
        tracked_regions = []
        for region in cf_frame.data.regions:
            tracked_regions.append(Region(proto_region=region))

        return tracked_regions

    def track_frame(self, frame, detections: List[Region], tracker: KalmanREID) -> List[Region]:
        """
        Track players in a single frame.

        Args:
            frame: Input frame
            detections: List of player detections
            tracker: Initialized tracker

        Returns:
            List of tracked regions
        """
        if not detections:
            return []

        # Extract player crops and compute embeddings
        crops = self._extract_player_crops(frame, detections)
        embeddings = self._compute_embeddings(crops)

        # Add embeddings to detections
        self._add_embeddings_to_detections(detections, embeddings)

        # Apply tracking
        tracked_regions = self._apply_tracking(detections, tracker)

        return tracked_regions

    def _create_result_data(self, tracked_detections: List[Region], metadata: Struct) -> dtFrame:
        """
        Create result data structure.

        Args:
            tracked_detections: List of tracked detections
            metadata: Additional metadata

        Returns:
            Combined result data
        """
        result_data = Frame()

        # Add tracked detections
        for region in tracked_detections:
            r = result_data.data.regions.add()
            r.CopyFrom(region.to_proto())

        # Add metadata
        result_data.data.metadata.CopyFrom(metadata)

        return dtFrame(proto_frame=result_data)


    # def _convert_dtframes_to_regions(self, detection_results: List[dtFrame]) -> List[List[Region]]:
    #     """
    #     Convert List[dtFrame] to List[List[Region]].

    #     Args:
    #         detection_results: List of dtFrame objects containing detection data

    #     Returns:
    #         List of lists containing Region objects for each frame
    #     """
    #     regions_per_frame = []

    #     for frame_result in detection_results:
    #         frame_regions = []

    #         # Extract regions from the dtFrame
    #         if hasattr(frame_result, 'proto') and hasattr(frame_result.proto, 'data'):
    #             # Access regions from proto data
    #             for region_proto in frame_result.proto.data.regions:
    #                 # Convert proto region back to Region object
    #                 region = Region(proto_region=region_proto)
    #                 frame_regions.append(region)
    #         elif hasattr(frame_result, 'data') and hasattr(frame_result.data, 'regions'):
    #             # Direct access to regions
    #             for region_proto in frame_result.data.regions:
    #                 region = Region(proto_region=region_proto)
    #                 frame_regions.append(region)

    #         regions_per_frame.append(frame_regions)

    #     return regions_per_frame

    # def _filter_player_detections(self, regions_per_frame: List[List[Region]]) -> List[List[Region]]:
    #     """
    #     Filter regions to only include players and referees.

    #     Args:
    #         regions_per_frame: List of lists containing Region objects

    #     Returns:
    #         Filtered list containing only player and referee regions
    #     """
    #     filtered_frames = []

    #     for frame_regions in regions_per_frame:
    #         player_regions = []

    #         for region in frame_regions:
    #             # Check if region has concepts and if it's a player or referee
    #             if region.data and region.data.concepts:
    #                 concept_names = [concept.name for concept in region.data.concepts]
    #                 if any(name in ['players', 'referee', 'player'] for name in concept_names):
    #                     player_regions.append(region)
    #             # Also check proto concepts if data concepts are empty
    #             elif hasattr(region, 'proto') and region.proto.data.concepts:
    #                 concept_names = [concept.name for concept in region.proto.data.concepts]
    #                 if any(name in ['players', 'referee', 'player'] for name in concept_names):
    #                     player_regions.append(region)

    #         filtered_frames.append(player_regions)

    #     return filtered_frames


    @ModelClass.method
    def predict(self, video: Video, detection_results: List[dtFrame], tracker_params: dict = None,
                max_frames: int = None) -> List[dtFrame]:
        """
        Process video and return tracking results.

        Args:
            video: Input video to process
            player_detections: List of player detections per frame
            tracker_params: Optional parameters for tracking
            max_frames: Maximum number of frames to process (None for all frames)

        Returns:
            List of processed frame results with tracking
        """
        results = []
        #TODO: Setup player detections from detection_results

        # Setup video stream
        if not video.bytes and not video.url:
            raise ValueError("Video must have either bytes or url set.")

        if video.url:
            stream = video_utils.stream_frames_from_url(video.url, download_ok=True)
        elif video.bytes:
            def _bytes_iterator():
                yield video.bytes
            stream = video_utils.stream_frames_from_bytes(_bytes_iterator())
        else:
            raise ValueError("Video must have either bytes or url set.")

        # Setup tracker
        tracker = self._setup_tracker(tracker_params)

        # Process each frame
        for frame_idx, frame in enumerate(stream):
            # Check frame limit
            if max_frames is not None and frame_idx >= max_frames:
                break

            logger.info(f"Processing frame {frame_idx}")

            try:
                # For standalone tracking, we need detections from somewhere
                # In a composed pipeline, this would come from the detection runner
                # For now, we'll create a placeholder - in practice, this would be
                # passed as input or obtained from another runner

                # This is a placeholder - in real usage, detections would come from detection runner
                detections = []  # Placeholder for detections

                # Track players
                tracked_detections = self.track_frame(frame, detections, tracker)

                # Create metadata
                metadata = Struct()
                metadata.update({
                    'tracked_count': len(tracked_detections),
                    'frame_index': frame_idx,
                    'tracker_type': 'KalmanREID'
                })

                # Create result
                result_data = self._create_result_data(tracked_detections, metadata)
                results.append(result_data)

            except Exception as e:
                logger.error(f"Error processing frame {frame_idx}: {e}")
                # Create error result for this frame
                error_metadata = Struct()
                error_metadata.update({'error': f"Frame processing failed: {str(e)}"})
                error_result = self._create_result_data([], error_metadata)
                results.append(error_result)

        logger.info(f"Processed {len(results)} frames")
        return results