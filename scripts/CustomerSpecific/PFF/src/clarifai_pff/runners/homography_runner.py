"""
Homography Runner for Field Perspective Correction

This module provides a standalone homography service that can be deployed independently
or composed with other runners for complete video processing pipelines.
"""

from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging
from time import perf_counter_ns
from contextlib import contextmanager

import cv2
import numpy as np

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types.data_types import Video, Region, Concept, Frame as dtFrame
import clarifai.utils.logging as logging_utils
from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from google.protobuf.struct_pb2 import Struct

from clarifai_pff.auto_homography import (
    FieldInfo, process_response, process_image, transform_points, is_convex_polygon,
    field_to_pixel, ProcessingConfig, gen_field, FIELD_INFOS, League, HomographyError, HomographyResult as _HomographyResult,
    compute_camera_motion
)
import clarifai_pff.utils.video as video_utils
import os
import scipy

logger = logging_utils.get_logger(logging.INFO, name=__name__)


@dataclass
class HomographyConfig:
    """Configuration for homography processing."""
    transforms: List[Dict[str, Any]]
    directional_threshold: float
    field_info: Any
    backprojection_error_threshold: float = 10.0
    condition_number_threshold: float = 1e12


@dataclass
class HomographyResult:
    """Result of homography computation with validation."""
    homography: _HomographyResult
    warnings: List[str]
    error: Optional[str] = None
    backprojection_error: Optional[float] = None
    condition_number: Optional[float] = None


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


class HomographyRunner(ModelClass):
    """
    Standalone homography runner for field perspective correction.

    This runner can be deployed independently or composed with other runners
    for complete video processing pipelines.
    """

    def __init__(self, folder: Optional[str] = None):
        super().__init__()
        self.folder = folder
        self.config: Optional[HomographyConfig] = None

    def _get_model_folder(self) -> str:
        """Get the model folder path."""
        return getattr(self, 'folder', False) or os.path.dirname(os.path.dirname(__file__))

    def load_model(self):
        """Initialize homography configuration."""
        # Initialize homography configuration
        self.config = HomographyConfig(
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

        logger.info("Homography configuration initialized successfully")

    def set_field_info(self, field_info):
        """
        Set custom field information for homography computation.

        Args:
            field_info: Field information object (e.g., FIELD_INFOS[League.NFL])
        """
        self.config.field_info = field_info
        logger.info("Field info updated successfully")

    def get_field_info(self):
        """
        Get current field information.

        Returns:
            Current field information object
        """
        return self.config.field_info

    def _validate_homography_result(self, homography_result: Any, frame_shape: Tuple[int, int]) -> HomographyResult:
        """
        Validate homography result and compute quality metrics.

        Args:
            homography_result: Raw homography result
            frame_shape: Frame dimensions (height, width)

        Returns:
            HomographyResult with validation metrics
        """
        warnings = []
        backprojection_error = None
        condition_number = None

        if homography_result.matrix is None:
            raise HomographyError("Failed to compute homography matrix. Not enough correspondence points or invalid data.")

        # Validate homography with backprojection error
        try:
            mask_indices = homography_result.mask.ravel() > 0
            if np.any(mask_indices):
                backproj = transform_points(
                    homography_result.field_points[mask_indices],
                    homography_result.matrix,
                    inverse=True
                )
                se = np.square(homography_result.image_points[mask_indices] - backproj)
                backprojection_error = float(np.mean(se))

                if backprojection_error > self.config.backprojection_error_threshold:
                    warnings.append(f"High backprojection error: {backprojection_error:.2f}")
        except Exception as e:
            warnings.append(f"Failed to compute backprojection error: {e}")

        # Compute condition number of the homography matrix
        try:
            condition_number = float(np.linalg.cond(homography_result.matrix))
            if condition_number > self.config.condition_number_threshold:
                warnings.append(f"Homography matrix condition number is too high: {condition_number:.2e}")
        except Exception as e:
            warnings.append(f"Failed to compute condition number: {e}")

        # Validate field of view
        try:
            h, w = frame_shape[:2]
            field_info = self.config.field_info
            field_img = gen_field(h, w, field_info, exclude_hash_marks=False)

            # Transform frame corners to field coordinates
            frame_corners = [(0, 0), (w, 0), (w, h), (0, h)]
            fov_pts = [field_to_pixel(*x, field_img, field_info)
                      for x in transform_points(frame_corners, homography_result.matrix)]

            if not is_convex_polygon(fov_pts):
                raise ValueError("Field of view is not convex")

        except Exception as e:
            warnings.append(f"Field of view validation failed: {e}")

        return HomographyResult(
            homography=homography_result,
            warnings=warnings,
            backprojection_error=backprojection_error,
            condition_number=condition_number
        )

    def _denormalize_detections(self, detections: List[Region], frame_shape: Tuple[int, int]):
        """
        Denormalize detection boxes for homography processing.

        Args:
            detections: List of detections with normalized coordinates
            frame_shape: Frame dimensions (width, height)
        """
        new_regions = []
        for region in detections:
            new_region = Region()
            new_region.proto.CopyFrom(region.proto)
            new_region.box = [coord * size for coord, size in zip(region.box, [*frame_shape] * 2)]
            new_regions.append(new_region)
        return new_regions

    def compute_homography(self, frame, field_element_detections: List[Region],
                          homography_params: Optional[Dict[str, Any]] = None, prev_frame = None, prev_homography: Optional[HomographyResult] = None) -> HomographyResult:
        """
        Compute homography matrix for field perspective correction.

        Args:
            frame: Input frame
            field_element_detections: Detected field elements
            homography_params: Optional parameters for homography computation

        Returns:
            HomographyResult with validation metrics

        Raises:
            ValueError: If insufficient detections for homography
            HomographyError: If homography computation fails
        """
        # Validate field_info is set
        if self.config.field_info is None:
            raise ValueError("Field info is not set. Please call set_field_info() or ensure default configuration is loaded.")

        # Create processing config
        if homography_params:
            # Merge provided parameters with default configuration
            merged_params = {
                'transforms': self.config.transforms,
                'directional_threshold': self.config.directional_threshold,
                'field_info': self.config.field_info
            }
            if not isinstance(homography_params['field_info'], FieldInfo):
                homography_params['field_info'] = FieldInfo(**homography_params['field_info'])
            # Override with provided parameters
            merged_params.update(homography_params)
            config = ProcessingConfig(**merged_params)
            logger.info(f"Using custom homography parameters with field_info: {config.field_info._asdict()}")
        else:
            config = ProcessingConfig(
                transforms=self.config.transforms,
                directional_threshold=self.config.directional_threshold,
                field_info=self.config.field_info
            )
            logger.info(f"Using default homography configuration with field_info: {type(self.config.field_info).__name__}")

        # Compute homography
        with timing_context("Homography computation"):
            try:
                if not field_element_detections:
                    raise HomographyResult(homography=None, warnings=["No field elements detected"])

                # Denormalize boxes for homography processing
                frame_array = frame.to_ndarray(format="rgb24")
                frame_size = frame_array.shape[:2][::-1]  # (width, height)
                
                field_element_detections = self._denormalize_detections(field_element_detections, frame_size)

                # Process hash yard detections
                yard_boxes, yard_labels, inner_boxes, up_edge_boxes = process_response(field_element_detections)

                # Convert frame to BGR for OpenCV consistency
                frame_bgr = frame.to_ndarray(format="bgr24")
                # Validate detection requirements
                if not yard_boxes:
                    raise ValueError("No yard lines detected in the image. Please check the image quality or configuration.")
                if not inner_boxes:
                    raise ValueError("No inner hash marks detected in the image. Please check the image quality or configuration.")
                
                result = process_image(
                    frame_bgr,
                    yard_boxes=np.array(yard_boxes, dtype=np.float32),
                    yard_labels=np.array(yard_labels, dtype=np.int32),
                    inner_boxes=np.array(inner_boxes, dtype=np.float32),
                    up_edge_boxes=np.array(up_edge_boxes, dtype=np.float32) if up_edge_boxes else np.array([], dtype=np.float32).reshape(0, 5),
                    config=config
                )
                # Smooth homography using previous frame's homography and camera motion
                # TODO: move away from threshold to proper state estimation and assimilation
                # TODO: cleanup
                if prev_frame is not None and prev_homography is not None:
                    camera_motion = compute_camera_motion(prev_frame.to_ndarray(format='bgr24'), frame_bgr)
                    hyp_homography_matrix = prev_homography.homography.matrix @ np.linalg.inv(camera_motion)

                    if result.homography.matrix is None:
                        logger.info(f"Frame {frame}: No homography computed, using previous frame's homography adjusted by camera motion")
                        result.homography.matrix = hyp_homography_matrix
                        result.homography.mask = prev_homography.homography.mask
                        result.homography.field_points = prev_homography.homography.field_points
                        result.homography.image_points = transform_points(
                            result.homography.field_points, 
                            result.homography.matrix, 
                            inverse=True
                        ) if result.homography.field_points else None
                        result.warnings.append("No homography computed, using previous frame's homography adjusted by camera motion")
                    else:
                        lie_dist = np.linalg.norm(scipy.linalg.logm(result.homography.matrix) - scipy.linalg.logm(hyp_homography_matrix))
                        logger.info(f"Frame {frame}: Lie distance = {lie_dist}")
                        if lie_dist > 5: #15:
                            result.homography.matrix = hyp_homography_matrix
                            result.homography.mask = prev_homography.homography.mask
                            result.homography.field_points = prev_homography.homography.field_points
                            result.homography.image_points = transform_points(
                                result.homography.field_points,
                                result.homography.matrix,
                                inverse=True
                            ) if result.homography.field_points is not None else None
                            result.warnings.append(f"High Lie distance ({lie_dist:.2f}), smoothing homography with camera motion")
            except Exception as e:
                if prev_frame is not None and prev_homography is not None:
                    camera_motion = compute_camera_motion(prev_frame.to_ndarray(format='bgr24'), frame.to_ndarray(format='bgr24'))
                    homography_matrix = prev_homography.homography.matrix @ np.linalg.inv(camera_motion)
                    field_points = prev_homography.homography.field_points
                    image_points = transform_points(field_points, homography_matrix, inverse=True) if field_points is not None else None
                    return HomographyResult(
                        homography=_HomographyResult(
                            matrix=homography_matrix,
                            image_points=image_points,
                            field_points=field_points,
                            mask=prev_homography.homography.mask
                        ),
                        warnings=["Homography computation failed, using previous frame's homography adjusted by camera motion. Error: " + str(e)],
                    )
                raise HomographyError(f"Error during homography computation: {e}")

            # Validate and return result
            final = self._validate_homography_result(result.homography, frame_bgr.shape)
            if final.condition_number is not None and final.condition_number < 1e10:
                prev_homography = final
            else:
                final = prev_homography  # Use previous if current is unstable
                if prev_frame is not None and prev_homography is not None:
                    camera_motion = compute_camera_motion(prev_frame.to_ndarray(format='bgr24'), frame.to_ndarray(format='bgr24'))
                    final.homography.matrix = prev_homography.homography.matrix @ np.linalg.inv(camera_motion)
                    final.homography.mask = prev_homography.homography.mask
                    final.homography.field_points = prev_homography.homography.field_points
                    final.homography.image_points = transform_points(
                        final.homography.field_points,
                        final.homography.matrix,
                        inverse=True
                    ) if final.homography.field_points is not None else None
                    final.warnings.append("Current homography unstable, using previous frame's homography adjusted by camera motion")
                    logger.info(final.warnings[-1])
            return final

    def _create_metadata(self, homography_result: HomographyResult) -> Struct:
        """
        Create metadata structure with homography information.

        Args:
            homography_result: Homography computation result

        Returns:
            Metadata structure
        """
        metadata = Struct()

        if homography_result is None:
            metadata.update({'error': 'Homography result is None'})
            return metadata

        if homography_result.homography is not None:
            metadata.update({
                'homography_matrix': homography_result.homography.matrix.tolist() if homography_result.homography.matrix is not None else None,
                'image_points': homography_result.homography.image_points.tolist() if homography_result.homography.image_points is not None else None,
                'field_points': homography_result.homography.field_points.tolist() if homography_result.homography.field_points is not None else None,
                'mask': homography_result.homography.mask.ravel().tolist() if homography_result.homography.mask is not None else None,
            })

        # Add validation metrics
        if homography_result.backprojection_error is not None:
            metadata.update({'backprojection_error': homography_result.backprojection_error})

        if homography_result.condition_number is not None:
            metadata.update({'condition_number': homography_result.condition_number})

        # Add warnings if present
        if homography_result.warnings:
            metadata.update({'warnings': homography_result.warnings})

        # Add error information if error occurred
        if homography_result.error:
            metadata.update({'error': homography_result.error})

        return metadata

    def _create_result_data(self, metadata: Struct) -> dtFrame:
        """
        Create result data structure.

        Args:
            metadata: Metadata structure

        Returns:
            Combined result data
        """
        result_data = Frame()

        # Add metadata
        result_data.data.metadata.CopyFrom(metadata)

        return dtFrame(proto_frame=result_data)

    @ModelClass.method
    def predict(self, video: Video, field_element_detections: List[List[Region]],
                homography_params: dict = None,
                max_frames: int = None) -> List[dtFrame]:
        """
        Process video and return homography results.

        Args:
            video: Input video to process
            field_element_detections: List of field element detections per frame
            homography_params: Optional parameters for homography computation
            max_frames: Maximum number of frames to process (None for all frames)

        Returns:
            List of processed frame results with homography
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

        # Process each frame
        for frame_idx, (frame, frame_detections) in enumerate(zip(stream, field_element_detections)):
            # Check frame limit
            if max_frames is not None and frame_idx >= max_frames:
                break

            logger.info(f"Processing frame {frame_idx}")

            try:
                # Compute homography
                with timing_context("Homography computation"):
                    try:
                        homography_result = self.compute_homography(frame, frame_detections, homography_params)
                    except Exception as e:
                        logger.error(f"Error computing homography: {e}")
                        homography_result = HomographyResult(
                            homography=None,
                            warnings=[],
                            error=str(e)
                        )

                # Create metadata
                metadata = self._create_metadata(homography_result)

                # Create result
                result_data = self._create_result_data(metadata)
                results.append(result_data)

            except Exception as e:
                logger.error(f"Error processing frame {frame_idx}: {e}")
                # Create error result for this frame
                error_metadata = Struct()
                error_metadata.update({'error': f"Frame processing failed: {str(e)}"})
                error_result = self._create_result_data(error_metadata)
                results.append(error_result)

        logger.info(f"Processed {len(results)} frames")
        return results