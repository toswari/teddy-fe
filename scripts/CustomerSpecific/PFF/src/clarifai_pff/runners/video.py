"""
Video Stream Model for Player, Hash Yard Detection, Tracking and Homography

This module provides a comprehensive video processing pipeline that combines:
- Player, referee and Hash yard line detection using YOLO model
- Player re-identification using embeddings
- Multi-object tracking with Kalman filters
- Homography estimation for field perspective correction
"""

from typing import Iterator, List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging
from time import perf_counter_ns

import onnx
import onnxruntime as ort
import os
import cv2
import numpy as np

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types.data_types import Video, Region, Concept, Frame as dtFrame
import clarifai.utils.logging as logging_utils
from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from google.protobuf.struct_pb2 import Struct

import clarifai_pff.utils.video as video_utils
from clarifai_pff.utils.transforms import letterbox
from clarifai_pff.tracking.reid import KalmanREID
from clarifai_pff.auto_homography import (
    process_response, process_image, transform_points, is_convex_polygon, field_to_pixel, ProcessingConfig,
    gen_field, FIELD_INFOS, League, HomographyError
)

logger = logging_utils.get_logger(logging.INFO, name=__name__)

@dataclass
class ModelConfig:
    """Configuration for model paths and labels."""
    model_folder: str
    detector_labels: Dict[int, str] = None

    def __post_init__(self):
        if self.detector_labels is None:
            self.detector_labels = {0: 'players', 1: 'referee', 2: 'inner', 3: 'low_edge', 4: 'up_edge',
                                    5: '10', 6: '20', 7: '30', 8: '40', 9: '50', 10: 'goal_line'}


@dataclass
class HomographyConfig:
    """Configuration for homography processing."""
    transforms: List[Dict[str, Any]]
    directional_threshold: float
    field_info: Any


class VideoStreamModel(ModelClass):
    """
    Advanced video processing model for sports analytics.

    This model performs comprehensive analysis of sports videos including:
    - Player, referee and field line detection (hash yards, goal lines, etc.)
    - Player re-identification and tracking
    - Field perspective correction via homography
    """

    def __init__(self, folder: Optional[str] = None):
        super().__init__()
        self.folder = folder
        self.config = None
        self.sessions = {}
        self.input_shapes = {}

    def _get_model_folder(self) -> str:
        """Get the model folder path."""
        return getattr(self, 'folder', False) or os.path.dirname(os.path.dirname(__file__))

    def _load_onnx_model(self, model_path: str, session_name: str) -> Tuple[ort.InferenceSession, Tuple[int, int]]:
        """
        Load an ONNX model and return the session and input shape.

        Args:
            model_path: Path to the ONNX model file
            session_name: Name for the session (used for logging)

        Returns:
            Tuple of (session, input_shape)
        """
        logger.info(f"Loading {session_name} model from {model_path}")

        # Load model to get input dimensions
        model = onnx.load(model_path)
        input_dims = [x.dim_value for x in model.graph.input[0].type.tensor_type.shape.dim[-2:]]
        input_shape = tuple(input_dims[::-1])  # Convert from (height, width) to (width, height)

        # Create inference session
        session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])

        logger.info(f"{session_name} model loaded with input shape: {input_shape}")
        return session, input_shape

    def load_model(self):
        """Load all required ONNX models and initialize configurations."""
        model_folder = self._get_model_folder()

        # Load detection model
        model_path = os.path.join(model_folder, '1', 'model.onnx')
        self.sessions['detection'], self.input_shapes['detection'] = self._load_onnx_model(
            model_path, "Detection"
        )

        # Load embedding model for re-identification
        embedder_path = os.path.join(model_folder, '1', 'embedder.onnx')
        self.sessions['embedder'], self.input_shapes['embedder'] = self._load_onnx_model(
            embedder_path, "Re-identification Embedder"
        )

        # Initialize label mappings
        self.config = ModelConfig(model_folder)

        # Initialize homography configuration
        self.default_homography_config = HomographyConfig(
            transforms=[
                dict(name='mean_blur_2d', kernel_size=3),
                dict(name='cvtGray'),
                dict(name='gaussian_adaptive_threshold', block_size=129, c=-16),
                dict(name='canny_edge', low_threshold=50, high_threshold=150),
                dict(name='hough_lines_xyxy', rho=1, theta=np.pi/180, threshold=150),
            ],
            directional_threshold=0.995,
            field_info=FIELD_INFOS[League.NFL]
        )

        logger.info("All models loaded successfully")

    def _preprocess_frame(self, frame, target_shape: Tuple[int, int]) -> Tuple[np.ndarray, float, np.ndarray, Tuple[int, int]]:
        """
        Preprocess frame for model inference.

        Args:
            frame: Input frame
            target_shape: Target shape for the model (width, height)

        Returns:
            Tuple of (preprocessed_input, scale_ratio, padding, original_size)
        """
        # Convert frame to numpy array
        frame_array = frame.to_ndarray(format="rgb24")
        original_size = frame_array.shape[:2][::-1]  # (width, height)

        # Apply letterbox transformation
        frame_array, ratio, dwdh = letterbox(frame_array, new_shape=target_shape, auto=False)

        # Convert to model input format
        frame_array = frame_array.transpose((2, 0, 1))  # HWC to CHW
        frame_array = np.expand_dims(frame_array, 0)  # Add batch dimension
        frame_array = np.ascontiguousarray(frame_array)

        # Normalize to [0, 1]
        input_data = frame_array.astype(np.float32) / 255.0

        return input_data, ratio, dwdh, original_size

    def _postprocess_detections(self, output: np.ndarray, ratio: float, dwdh: np.ndarray,
                               original_size: Tuple[int, int], label_map: Dict[int, str]) -> List[Region]:
        """
        Postprocess model outputs to extract bounding boxes and create Region objects.

        Args:
            output: Raw model output
            ratio: Scale ratio from preprocessing
            dwdh: Padding values from preprocessing
            original_size: Original frame size (width, height)
            label_map: Mapping from class IDs to label names

        Returns:
            List of Region objects
        """
        # Extract bounding boxes (last 6 columns: x1, y1, x2, y2, class, confidence)
        boxes = output[:, -6:-2]
        classes = output[:, -2]
        scores = output[:, -1]

        # Convert boxes to numpy array
        boxes = np.array(boxes)

        # Remove padding and scale back to original size
        boxes -= np.array(dwdh * 2)
        boxes /= ratio

        # Clip boxes to image boundaries
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(min=0, max=original_size[0])
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(min=0, max=original_size[1])

        # Normalize to [0, 1] range
        boxes /= np.array([*original_size] * 2)

        # Create Region objects
        regions = []
        for box, cls, score in zip(boxes, classes, scores):
            class_id = int(cls)
            region = Region(
                box=box.tolist(),
                concepts=[Concept(
                    id=str(class_id),
                    name=label_map[class_id],
                    value=float(score)
                )]
            )
            regions.append(region)

        return regions

    def _run_detection_model(self, input_data: np.ndarray, model_name: str) -> np.ndarray:
        """
        Run inference on a detection model.

        Args:
            input_data: Preprocessed input data
            model_name: Name of the model to run

        Returns:
            Model output
        """
        session = self.sessions[model_name]
        input_name = session.get_inputs()[0].name

        start_time = perf_counter_ns()
        output = session.run(None, {input_name: input_data})
        inference_time = perf_counter_ns() - start_time

        logger.info(f"{model_name} inference took {inference_time/1e9} s")
        return output[0]  # Return first output

    def predict_frame(self, frame) -> Tuple[List[Region], List[Region]]:
        """
        Process a single frame to detect players and field elements.

        Args:
            frame: Input frame

        Returns:
            Tuple of (player_detections, hash_yard_detections)
        """
        # Preprocess frame for detection models
        input_data, ratio, dwdh, original_size = self._preprocess_frame(
            frame, self.input_shapes['detection']
        )

        # Run detection
        detection_output = self._run_detection_model(input_data, 'detection')
        detections = self._postprocess_detections(
            detection_output, ratio, dwdh, original_size, self.config.detector_labels
        )

        # Filter detections for players and referees
        player_detections = [region for region in detections if region.concepts[0].name in ['players', 'referee']]
        hash_yard_detections = [region for region in detections if region.concepts[0].name not in ['players', 'referee']]

        return player_detections, hash_yard_detections

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
            crop = cv2.resize(crop, self.input_shapes['embedder'])

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

        start_time = perf_counter_ns()
        embeddings = self.sessions['embedder'].run(
            None, {self.sessions['embedder'].get_inputs()[0].name: crops}
        )[0]
        embedding_time = perf_counter_ns() - start_time

        logger.info(f"Embeddings shape: {embeddings.shape}")
        logger.info(f"Embedding computation took {embedding_time/1e9} s")

        return embeddings

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

    def _compute_homography(self, frame, hash_yard_detections: List[Region],
                            homography_params: dict = None) -> Optional[Any]:
        """
        Compute homography matrix for field perspective correction.

        Args:
            frame: Input frame
            hash_yard_detections: Detected field elements

        Returns:
            Homography result or None if insufficient detections
        """
        if not hash_yard_detections:
            return None

        warnings = []
        homography_result = None

        # Denormalize boxes for homography processing
        frame_array = frame.to_ndarray(format="rgb24")
        frame_size = frame_array.shape[:2][::-1]  # (width, height)

        for region in hash_yard_detections:
            region.box = [coord * size for coord, size in zip(region.box, [*frame_size] * 2)]

        # Process hash yard detections
        yard_boxes, yard_labels, inner_boxes, up_edge_boxes = process_response(hash_yard_detections)

        # Check if we have sufficient detections for homography
        if not len(yard_boxes):
            raise ValueError("No yard lines detected in the image. Please check the image quality or configuration.")
        if not len(inner_boxes):
            raise ValueError("No inner hash marks detected in the image. Please check the image quality or configuration.")

        # Convert frame to BGR for OpenCV consistency
        frame_bgr = frame.to_ndarray(format="bgr24")

        # Create processing config
        if homography_params:
            config = ProcessingConfig(**homography_params)
        else:
            config = ProcessingConfig(
                transforms=self.default_homography_config.transforms,
                directional_threshold=self.default_homography_config.directional_threshold,
                field_info=self.default_homography_config.field_info
            )

        # Compute homography
        try:
          result = process_image(
              frame_bgr,
              yard_boxes=np.array(yard_boxes, dtype=np.float32),
              yard_labels=np.array(yard_labels, dtype=np.int32),
              inner_boxes=np.array(inner_boxes, dtype=np.float32),
              up_edge_boxes=np.array(up_edge_boxes, dtype=np.float32) if up_edge_boxes else np.array([], dtype=np.float32).reshape(0, 5),
              config=config
          )
        except Exception as e:
          raise HomographyError(f"Error during homography computation: {e}")

        homography_result = result.homography
        warnings = result.warnings

        if homography_result.matrix is None:
            raise HomographyError("Failed to compute homography matrix. Not enough correspondence points or invalid data.")

        # Validate homography with backprojection error
        backproj = transform_points(
            homography_result.field_points[homography_result.mask.ravel() > 0],
            homography_result.matrix,
            inverse=True
        )
        se = np.square(homography_result.image_points[homography_result.mask.ravel() > 0] - backproj)
        mse = np.mean(se)
        if mse > 10:
            warnings.append(HomographyError(
                f"High backprojection error: {mse}"
            ))

        # compute condition number of the homography matrix
        # if the condition number is too high, it indicates numerical instability
        # and the homography may not be reliable (TODO)
        cond = np.linalg.cond(homography_result.matrix)
        if cond > 1e12:
            warnings.append(HomographyError(
                f"Homography matrix condition number is too high: {cond}"
            ))

        # Field image generation
        h, w = frame_bgr.shape[:2]
        field_info = config.field_info
        field_img = gen_field(h, w, field_info, exclude_hash_marks=False)
        fov_pts = [field_to_pixel(*x, field_img, field_info) for x in transform_points([(0, 0), (w, 0), (w, h), (0, h)], homography_result.matrix)]
        # Check if fov_pts forms a convex polygon

        is_convex = is_convex_polygon(fov_pts)
        if not is_convex:
            raise ValueError("Field of view is not convex")

        return homography_result, warnings

    def _create_metadata(self, homography_result, warnings, error=False, error_message=None) -> Struct:
        """
        Create metadata structure with homography information.

        Args:
            homography_result: Homography computation result
            warnings: List of warnings or errors
            error: Boolean indicating if there was an error in homography computation
            error_message: Error message if error occurred
        Returns:
            Metadata structure
        """
        metadata = Struct()

        if homography_result is not None:
            metadata.update({
                'homography_matrix': homography_result.matrix.tolist() if homography_result.matrix is not None else None,
                'image_points': homography_result.image_points.tolist() if homography_result.image_points is not None else None,
                'field_points': homography_result.field_points.tolist() if homography_result.field_points is not None else None,
                'mask': homography_result.mask.ravel().tolist() if homography_result.mask is not None else None,
            })

        # Add warnings if present
        if warnings:
            warning_messages = []
            for warning in warnings:
                # Handle different warning types
                if hasattr(warning, 'message'):
                    warning_messages.append(warning.message)
                elif isinstance(warning, str):
                    warning_messages.append(warning)
                else:
                    warning_messages.append(str(warning))

            metadata.update({'warnings': warning_messages})

        # Add error information if error occurred
        if error:
            if error_message:
                metadata.update({'error': str(error_message)})
            else:
                metadata.update({'error': 'An error occurred during homography computation'})

        return metadata

    def _create_result_data(self, detections: List[Region], metadata: Struct) -> Data:
        """
        Create final result data structure.

        Args:
            detections: List of detections
            metadata: Metadata structure

        Returns:
            Combined result data
        """
        result_data = Frame()

        # Add regions
        for region in detections:
            r = result_data.data.regions.add()
            r.CopyFrom(region.to_proto())

        # Add metadata
        result_data.data.metadata.CopyFrom(metadata)

        return dtFrame(proto_frame=result_data)

    def _setup_video_stream(self, video: Video) -> Iterator:
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
            def _bytes_iterator():
                yield video.bytes
            return video_utils.stream_frames_from_bytes(_bytes_iterator())
        else:
            raise ValueError("Video must have either bytes or url set.")

    def _setup_tracker(self, tracker_params: Optional[Dict[str, Any]]):
        """
        Setup tracking if parameters are provided.

        Args:
            tracker_params: Tracker configuration parameters

        Returns:
            Initialized tracker or None
        """
        if tracker_params is None:
            return None

        # Add reid model path to tracker params
        reid_model_path = os.path.join(self._get_model_folder(), '1', 'reid.skl')
        tracker_params["reid_model_path"] = reid_model_path

        # Initialize tracker
        tracker = KalmanREID(**tracker_params)
        tracker.init_state()

        return tracker

    @ModelClass.method
    def predict(
        self,
        video: Video,
        tracker_params: dict = None,
        homography_params: dict = None,
        max_frames: int = None
    ) -> List[dtFrame]:
        """
        Process video and return detection results with tracking and homography.

        Args:
            video: Input video to process
            tracker_params: Optional parameters for multi-object tracking
            homography_params: Optional parameters for homography computation
            max_frames: Maximum number of frames to process (None for all frames)

        Returns:
            List of processed frame results with detections, embeddings, tracking, and homography
        """
        results = []

        # Setup video stream
        stream = self._setup_video_stream(video)

        # Setup tracker if parameters provided
        tracker = self._setup_tracker(tracker_params)

        # Process each frame
        for frame_idx, frame in enumerate(stream):
            # Check frame limit
            if max_frames is not None and frame_idx >= max_frames:
                break

            logger.info(f"Processing frame {frame_idx}")

            # Detect players and field elements
            player_detections, hash_yard_detections = self.predict_frame(frame)

            # Extract player crops and compute embeddings
            if player_detections:
                crops = self._extract_player_crops(frame, player_detections)
                embeddings = self._compute_embeddings(crops)

                # Add embeddings to detections
                for region, embedding in zip(player_detections, embeddings):
                    emb = region.proto.data.embeddings.add()
                    emb.vector.extend(embedding.tolist())

            # Apply tracking if enabled
            if tracker is not None:
                player_detections = self._apply_tracking(player_detections, tracker)

            # Compute homography
            start = perf_counter_ns()
            try:
                homography_result, warnings = self._compute_homography(frame, hash_yard_detections, homography_params)
                # Create metadata
                metadata = self._create_metadata(homography_result, warnings, error=False)
            except Exception as e:
                logger.error(f"Error computing homography: {e}")
                homography_result, warnings = None, []
                metadata = self._create_metadata(homography_result, warnings, error=True, error_message=str(e))
            end = perf_counter_ns()
            logger.info(f"Homography computation took {(end - start)/1e9} s")

            # Create final result
            result_data = self._create_result_data(player_detections, metadata)
            results.append(result_data)

        logger.info(f"Processed {len(results)} frames")
        return results