from typing import Iterator

from clarifai.runners.models.model_class import ModelClass
from clarifai_grpc.grpc.api import service_pb2
from clarifai_grpc.grpc.api.status import status_code_pb2


from clarifai.runners.utils.data_types.data_types import Video, Region, Concept
from typing import List, Optional

import onnx
import onnxruntime as ort
import os
import cv2
import numpy as np

import logging
from time import perf_counter_ns

import clarifai_pff.utils.video as video_utils
from clarifai_pff.utils.transforms import letterbox
from clarifai_pff.tracking.reid import KalmanREID
from clarifai_grpc.grpc.api.resources_pb2 import Frame

logger = logging.getLogger(__name__)

class VideoStreamModel(ModelClass):
  """
  Example model that processes a video stream and returns the time and shape of each frame.
  """

  def load_model(self):
    model_folder = os.path.dirname(os.path.dirname(__file__))
    model_path = os.path.join(model_folder, '1', 'model.onnx')
    m = onnx.load(model_path)
    input_yx = [x.dim_value for x in m.graph.input[0].type.tensor_type.shape.dim[-2:]]

    self.im_xy = input_yx[::-1]
    self.session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])

    embedder_path = os.path.join(model_folder, '1', 'embedder.onnx')
    m = onnx.load(embedder_path)
    input_yx = [x.dim_value for x in m.graph.input[0].type.tensor_type.shape.dim[-2:]]

    self.embedder_im_xy = input_yx[::-1]
    self.embedder_session = ort.InferenceSession(embedder_path, providers=['CUDAExecutionProvider'])

    self.id2label = {i: c['name'] for i,c in enumerate([dict(name='players'), dict(name='referee')])}

  def predict_frame(self, frame) -> List[Region]:
    # Process each frame
    frame_array = frame.to_ndarray(format="rgb24")
    ori_size = frame_array.shape[:2][::-1]  # (width, height)
    frame_array, ratio, dwdh = letterbox(frame_array, new_shape=self.im_xy, auto=False)
    frame_array = frame_array.transpose((2, 0, 1))
    frame_array = np.expand_dims(frame_array, 0)
    frame_array = np.ascontiguousarray(frame_array)
    input_data = frame_array.astype(np.float32)
    input_data /= 255

    input_name = self.session.get_inputs()[0].name

    start = perf_counter_ns()
    outputs = self.session.run(None, {input_name: input_data})
    logger.info("inference took {} ns".format(perf_counter_ns() - start))

    result = []
    for idx,output in enumerate(outputs):
        boxes = output[:, -6:-2]
        boxes = np.array(boxes)
        boxes -= np.array(dwdh*2)
        boxes /= ratio
        boxes[:,[0,2]] = boxes[:,[0,2]].clip(min=0, max=ori_size[0])
        boxes[:,[1,3]] = boxes[:,[1,3]].clip(min=0, max=ori_size[1])
        boxes /= np.array([*ori_size]*2)
        
        classes = output[:, -2]
        scores = output[:, -1]

        result_inner = []
        for box, cls, score in zip(boxes, classes, scores):
            cls_id = int(cls)
            result_inner.append(
                Region(box=box.tolist(), concepts=[Concept(id=str(cls_id), name=self.id2label[cls_id], value=score)])
            )
        result.append(result_inner)

    return result[0]

  @ModelClass.method
  def predict(
     self, 
     video: Video, 
     tracker_params: dict = None,
     max_frames: int = None
  ) -> List[List[Region]]:
    results = []

    def _bytes_iterator():
      for v in [video]:
        yield v.bytes  # not actually base64, but the raw bytes

    if not video.bytes and not video.url:
      raise ValueError("Video must have either bytes or url set.")
    elif video.url:
       stream = video_utils.stream_frames_from_url(video.url, download_ok=True)
    elif video.bytes:
       stream = video_utils.stream_frames_from_bytes(_bytes_iterator())
    else:
      raise ValueError("Video must have either bytes or url set.")

    if tracker_params is not None:
      tracker = KalmanREID(**tracker_params)
      tracker.init_state()
    for i, frame in enumerate(stream):
        if max_frames is not None and i >= max_frames:
          break
        result = self.predict_frame(frame)

        frame_array = frame.to_ndarray(format="rgb24")
        frame_size = frame_array.shape[:2][::-1]  # (width, height)
        crops = []
        for region in result:
          x, y, xx, yy = [x*y for x,y in zip(region.box, [*frame_size]*2)]
          crop = frame_array[int(y):int(yy), int(x):int(xx)]
          crop = cv2.resize(crop, (self.embedder_im_xy[0], self.embedder_im_xy[1]))
          crop = np.ascontiguousarray(crop, dtype=np.float32)
          crop = np.moveaxis(crop, -1, 0)  # Change from HWC to CHW format
          crop = crop / 255.0  # Normalize to [0, 1] for ONNX model input
          crops.append(crop)
        crops = np.array(crops)
        
        embedding_start = perf_counter_ns()
        embeddings = self.embedder_session.run(
            None,
            {self.embedder_session.get_inputs()[0].name: crops}
        )[0]
        logger.info("embedding took {} ns".format(perf_counter_ns() - embedding_start))
        logger.info("embeddings shape: {}".format(embeddings[0].shape))
        for region, embedding in zip(result, embeddings):
          emb = region.proto.data.embeddings.add()
          emb.vector.extend(embedding.tolist())
        
        if tracker_params is not None:
          cf_frame = Frame()
          for region in result:
              r = cf_frame.data.regions.add()
              r.CopyFrom(region.to_proto())
              # to_proto does not set this, but the tracker expects it
              r.value = region.concepts[0].value
          tracker(cf_frame.data)

          result = []
          for region in cf_frame.data.regions:
            result.append(Region(proto_region=region))

        results.append(result)

    return results