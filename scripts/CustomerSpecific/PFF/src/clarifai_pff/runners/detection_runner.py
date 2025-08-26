"""
Detection Runner for Player and Field Element Detection

This module provides a standalone detection service that can be deployed independently
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
from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from google.protobuf.struct_pb2 import Struct

from clarifai_pff.utils.transforms import letterbox
import clarifai_pff.utils.video as video_utils

logger = logging_utils.get_logger(logging.INFO, name=__name__)


@dataclass
class DetectionConfig:
    """Configuration for detection model and labels."""
    model_folder: str
    detector_labels: Optional[Dict[int, str]] = None
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.4

    def __post_init__(self):
        if self.detector_labels is None:
            self.detector_labels = {
                0: 'players', 1: 'referee', 2: 'inner', 3: 'low_edge', 4: 'up_edge',
                5: '10', 6: '20', 7: '30', 8: '40', 9: '50', 10: 'goal_line'
            }


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


class DetectionRunner(ModelClass):
    """
    Standalone detection runner for player and field element detection.

    This runner can be deployed independently or composed with other runners
    for complete video processing pipelines.
    """

    def __init__(self, folder: Optional[str] = None):
        super().__init__()
        self.folder = folder
        self.config: Optional[DetectionConfig] = None
        self.session: Optional[ort.InferenceSession] = None
        self.input_shape: Optional[Tuple[int, int]] = None

    def _get_model_folder(self) -> str:
        """Get the model folder path."""
        return getattr(self, 'folder', False) or os.path.dirname(os.path.dirname(__file__))

    def _load_onnx_model(self, model_path: str) -> Tuple[ort.InferenceSession, Tuple[int, int]]:
        """
        Load an ONNX model and return the session and input shape.

        Args:
            model_path: Path to the ONNX model file

        Returns:
            Tuple of (session, input_shape)

        Raises:
            FileNotFoundError: If model file doesn't exist
            RuntimeError: If model loading fails
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(f"Loading detection model from {model_path}")

        try:
            # Load model to get input dimensions
            model = onnx.load(model_path)
            input_dims = [x.dim_value for x in model.graph.input[0].type.tensor_type.shape.dim[-2:]]
            input_shape = tuple(input_dims[::-1])  # Convert from (height, width) to (width, height)

            # Create inference session
            session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])

            logger.info(f"Detection model loaded with input shape: {input_shape}")
            return session, input_shape

        except Exception as e:
            raise RuntimeError(f"Failed to load detection model: {e}")

    def load_model(self):
        """Load the detection ONNX model and initialize configuration."""
        model_folder = self._get_model_folder()
        model_path = os.path.join(model_folder, '1', 'model.onnx')

        self.session, self.input_shape = self._load_onnx_model(model_path)
        self.config = DetectionConfig(model_folder)

        logger.info("Detection model loaded successfully")

    def _preprocess_frame(self, frame) -> Tuple[np.ndarray, float, np.ndarray, Tuple[int, int]]:
        """
        Preprocess frame for model inference.

        Args:
            frame: Input frame

        Returns:
            Tuple of (preprocessed_input, scale_ratio, padding, original_size)
        """
        # Convert frame to numpy array
        frame_array = frame.to_ndarray(format="rgb24")
        original_size = frame_array.shape[:2][::-1]  # (width, height)

        # Apply letterbox transformation
        frame_array, ratio, dwdh = letterbox(frame_array, new_shape=self.input_shape, auto=False)

        # Convert to model input format
        frame_array = frame_array.transpose((2, 0, 1))  # HWC to CHW
        frame_array = np.expand_dims(frame_array, 0)  # Add batch dimension
        frame_array = np.ascontiguousarray(frame_array)

        # Normalize to [0, 1]
        input_data = frame_array.astype(np.float32) / 255.0

        return input_data, ratio, dwdh, original_size

    def _postprocess_detections(self, output: np.ndarray, ratio: float, dwdh: np.ndarray,
                               original_size: Tuple[int, int]) -> List[Region]:
        """
        Postprocess model outputs to extract bounding boxes and create Region objects.

        Args:
            output: Raw model output
            ratio: Scale ratio from preprocessing
            dwdh: Padding values from preprocessing
            original_size: Original frame size (width, height)

        Returns:
            List of Region objects
        """
        # Extract bounding boxes (last 6 columns: x1, y1, x2, y2, class, confidence)
        boxes = output[:, -6:-2]
        classes = output[:, -2]
        scores = output[:, -1]

        # Filter by confidence threshold
        confidence_mask = scores >= self.config.confidence_threshold
        if not np.any(confidence_mask):
            return []

        boxes = boxes[confidence_mask]
        classes = classes[confidence_mask]
        scores = scores[confidence_mask]

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
                    name=self.config.detector_labels[class_id],
                    value=float(score)
                )]
            )
            regions.append(region)

        return regions

    def _run_detection(self, input_data: np.ndarray) -> np.ndarray:
        """
        Run inference on the detection model.

        Args:
            input_data: Preprocessed input data

        Returns:
            Model output
        """
        input_name = self.session.get_inputs()[0].name

        with timing_context("Detection inference"):
            output = self.session.run(None, {input_name: input_data})

        return output[0]  # Return first output

    def detect_frame(self, frame) -> Tuple[List[Region], List[Region]]:
        """
        Detect players and field elements in a single frame.

        Args:
            frame: Input frame

        Returns:
            Tuple of (player_detections, field_element_detections)
        """
        # Preprocess frame
        input_data, ratio, dwdh, original_size = self._preprocess_frame(frame)

        # Run detection
        detection_output = self._run_detection(input_data)
        detections = self._postprocess_detections(detection_output, ratio, dwdh, original_size)

        # Filter detections by type
        player_detections = [region for region in detections if region.concepts[0].name in ['players', 'referee']]
        field_element_detections = [region for region in detections if region.concepts[0].name not in ['players', 'referee']]

        return player_detections, field_element_detections

    def _create_result_data(self, player_detections: List[Region], field_element_detections: List[Region]) -> dtFrame:
        """
        Create result data structure.

        Args:
            player_detections: List of player detections
            field_element_detections: List of field element detections

        Returns:
            Combined result data
        """
        result_data = Frame()

        # Add player detections
        for region in player_detections:
            r = result_data.data.regions.add()
            r.CopyFrom(region.to_proto())

        # Add field element detections
        for region in field_element_detections:
            r = result_data.data.regions.add()
            r.CopyFrom(region.to_proto())

        # Add metadata
        metadata = Struct()
        metadata.update({
            'detection_count': len(player_detections) + len(field_element_detections),
            'player_count': len(player_detections),
            'field_element_count': len(field_element_detections),
            'confidence_threshold': self.config.confidence_threshold
        })
        result_data.data.metadata.CopyFrom(metadata)

        return dtFrame(proto_frame=result_data)

    @ModelClass.method
    def predict(self, video: Video, max_frames: int = None) -> List[dtFrame]:
        """
        Process video and return detection results.

        Args:
            video: Input video to process
            max_frames: Maximum number of frames to process (None for all frames)

        Returns:
            List of processed frame results with detections
        """
        results = []

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

        # Process each frame
        for frame_idx, frame in enumerate(stream):
            # Check frame limit
            if max_frames is not None and frame_idx >= max_frames:
                break

            logger.info(f"Processing frame {frame_idx}")

            try:
                # Detect players and field elements
                player_detections, field_element_detections = self.detect_frame(frame)

                # Create result
                result_data = self._create_result_data(player_detections, field_element_detections)
                results.append(result_data)

            except Exception as e:
                logger.error(f"Error processing frame {frame_idx}: {e}")
                # Create error result for this frame
                error_metadata = Struct()
                error_metadata.update({'error': f"Frame processing failed: {str(e)}"})
                error_result = self._create_result_data([], [])
                error_result.data.metadata.CopyFrom(error_metadata)
                results.append(error_result)

        logger.info(f"Processed {len(results)} frames")
        return results