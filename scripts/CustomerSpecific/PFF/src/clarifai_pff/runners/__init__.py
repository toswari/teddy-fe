"""
Runners Package for Video Processing Components

This package provides modular runners for different video processing tasks:
- DetectionRunner: Player and field element detection
- TrackingRunner: Player re-identification and multi-object tracking  
- HomographyRunner: Field perspective correction
- CompositeRunner: Complete pipeline orchestration
"""

from .detection_runner import DetectionRunner, DetectionConfig
from .tracking_runner import TrackingRunner, TrackingConfig
from .homography_runner import HomographyRunner, HomographyConfig, HomographyResult
from .composite_runner import CompositeRunner

__all__ = [
    'DetectionRunner',
    'DetectionConfig', 
    'TrackingRunner',
    'TrackingConfig',
    'HomographyRunner',
    'HomographyConfig',
    'HomographyResult',
    'CompositeRunner'
] 