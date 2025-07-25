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
from clarifai_pff.tracking.reid import KalmanREID
from clarifai_grpc.grpc.api.resources_pb2 import Frame

logger = logging.getLogger(__name__)

def letterbox(im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleup=True, stride=32):
  # Resize and pad image while meeting stride-multiple constraints
  shape = im.shape[:2]  # current shape [height, width]
  if isinstance(new_shape, int):
      new_shape = (new_shape, new_shape)

  # Scale ratio (new / old)
  r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
  if not scaleup:  # only scale down, do not scale up (for better val mAP)
      r = min(r, 1.0)

  # Compute padding
  new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
  dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

  if auto:  # minimum rectangle
      dw, dh = np.mod(dw, stride), np.mod(dh, stride)  # wh padding

  dw /= 2  # divide padding into 2 sides
  dh /= 2

  if shape[::-1] != new_unpad:  # resize
      im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
  top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
  left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
  im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
  return im, r, (dw, dh)

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
  def predict(self, video: Video, tracker_params: dict = None, max_frames: int = None) -> List[List[Region]]:
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
        if tracker_params is not None:
          frame_array = frame.to_ndarray(format="rgb24")
          frame_size = frame_array.shape[:2][::-1]  # (width, height)
          cf_frame = Frame()
          for region in result:
              r = cf_frame.data.regions.add()
              r.region_info.bounding_box.left_col = region.box[0]
              r.region_info.bounding_box.top_row = region.box[1]
              r.region_info.bounding_box.right_col = region.box[2]
              r.region_info.bounding_box.bottom_row = region.box[3]
              r.value = region.concepts[0].value
              r.data.concepts.add(name=region.concepts[0].name, value=r.value)

              x, y, xx, yy = [x*y for x,y in zip(region.box, [*frame_size]*2)]
              crop = frame_array[int(y):int(yy), int(x):int(xx)]
              embedding = crop.mean(axis=(0, 1)).flatten()  # Simple mean embedding
              emb = r.data.embeddings.add()
              emb.vector.extend(embedding)
              
          tracker(cf_frame.data)

          result = []
          for region in cf_frame.data.regions:
            result.append(
                Region(
                    box=[
                        region.region_info.bounding_box.left_col,
                        region.region_info.bounding_box.top_row,
                        region.region_info.bounding_box.right_col,
                        region.region_info.bounding_box.bottom_row
                    ],
                    concepts=[Concept(name=region.data.concepts[0].name, value=region.value)],
                    track_id=region.track_id
                )
            )

        results.append(result)

    return results
