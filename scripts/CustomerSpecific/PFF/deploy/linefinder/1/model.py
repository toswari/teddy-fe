import asyncio
import traceback
from typing import List
from clarifai.runners.models.model_class import ModelClass
import os

from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Image, Region, Concept
from clarifai_grpc.grpc.api import resources_pb2
import cv2
import numpy as np
from lines import find_yard_lines, Lines, WarpError

import logging
from clarifai.utils.logging import get_logger
logger = get_logger()

def ensure_event_loop():
    try:
        # Check if an event loop is already running
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

class MyModel(ModelClass):
    """A custom model implementation using ModelClass."""

    def load_model(self):
        """Load the model here.
        # TODO: please fill in
        # Add your model loading logic here
        """
        # Initialize detection runner
        self.folder = os.path.dirname(os.path.dirname(__file__))

        self.detector_url = "https://clarifai.com/pff-org/labelstudio-unified/models/unified-model"

    @ModelClass.method
    def predict(
        self,
        image: Image,
    ) -> List[Region]:
        image_array = image.to_numpy()[:,:,::-1] # RGB_2_BGR

        loop = ensure_event_loop()
        model = Model(url=self.detector_url)
        try:
            result = model.predict(image)
        finally:
            loop.close()

        
        yard_box_idx = [i for i, r in enumerate(result) if r.concepts[0].name in {'10', '20', '30', '40', '50'}]
        yard_boxes = np.array(
            [np.array(result[i].box) * np.array([image_array.shape[1], image_array.shape[0], image_array.shape[1], image_array.shape[0]]) for i in yard_box_idx]
        )
        yard_boxes_xywh = yard_boxes.copy()
        yard_boxes_xywh[:, 2] = yard_boxes[:, 2] - yard_boxes[:, 0]
        yard_boxes_xywh[:, 3] = yard_boxes[:, 3] - yard_boxes[:, 1]

        try:
            lines = Lines.hough(image_array)
        except Exception as e:
            logger.error(f"Error in Hough transform: {e}, {traceback.format_exc()}")
            lines = Lines([], image_array.shape[1], image_array.shape[0])

        try:
            yard_lines = find_yard_lines(lines, yard_boxes_xywh)
        except WarpError:
            yard_lines = Lines([], image_array.shape[1], image_array.shape[0])

        result = [
            Region(proto_region=
                resources_pb2.Region(
                    region_info=resources_pb2.RegionInfo(
                        polygon=resources_pb2.Polygon(points=[
                            resources_pb2.Point(row=y1/image_array.shape[0], col=x1/image_array.shape[1]),
                            resources_pb2.Point(row=y2/image_array.shape[0], col=x2/image_array.shape[1]),
                            resources_pb2.Point(row=y2/image_array.shape[0], col=x2/image_array.shape[1]),
                            resources_pb2.Point(row=y1/image_array.shape[0], col=x1/image_array.shape[1]),
                        ])
                    ),
                    data=resources_pb2.Data(
                        concepts=[
                            resources_pb2.Concept(id="line", name="line", value=1.0)
                        ]
                    )
                ),
            )
            for x1, y1, x2, y2 in yard_lines.xyxys.astype(int).tolist()
        ]

        return result