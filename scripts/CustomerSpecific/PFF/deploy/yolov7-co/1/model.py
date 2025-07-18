import logging
import numpy as np
import onnx
import onnxruntime as ort
import os
import yaml
import cv2

from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types import Image, Concept, Region
from io import BytesIO
from PIL import Image as PILImage
from time import perf_counter_ns
from typing import List

ort.set_default_logger_severity(1)
ort.set_default_logger_verbosity(1)

logger = logging.getLogger()

class MyRunner(ModelClass):
    def load_model(self):
        model_folder = os.path.dirname(os.path.dirname(__file__))
        model_path = os.path.join(model_folder, '1', 'model.onnx')
        m = onnx.load(model_path)
        input_yx = [x.dim_value for x in m.graph.input[0].type.tensor_type.shape.dim[-2:]]

        self.im_xy = input_yx[::-1]
        self.session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])

        with open(os.path.join(model_folder, 'config.yaml'), 'r') as f:
            concepts = yaml.safe_load(f)['concepts']

        self.id2label = {i: c['name'] for i,c in enumerate(concepts)}

    @ModelClass.method
    def predict(self, image: Image, relative: bool=True) -> List[Region]:
        image = PILImage.open(BytesIO(image.bytes)).convert("RGB")
        ori_size = image.size
        image = np.array(image)
        image, ratio, dwdh = self.letterbox(image, new_shape=self.im_xy ,auto=False)
        image = image.transpose((2, 0, 1))
        image = np.expand_dims(image, 0)
        image = np.ascontiguousarray(image)
        input_data = image.astype(np.float32)
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
            if not relative:
                boxes *= np.array([*ori_size]*2)
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


    def letterbox(self, im, new_shape=(640, 640), color=(114, 114, 114), auto=True, scaleup=True, stride=32):
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

def infer(model_path, image):
    m = onnx.load(model_path)
    input_yx = [x.dim_value for x in m.graph.input[0].type.tensor_type.shape.dim[-2:]]

    image = image.convert('RGB')
    image = image.resize(input_yx[::-1])

    input_data = np.array(image, dtype=np.float32)
    input_data = input_data.transpose(2, 0, 1)
    input_data = input_data / 255.0
    input_data = np.expand_dims(input_data, axis=0)

    session = ort.InferenceSession(model_path, providers=['CUDAExecutionProvider'])
    input_name = session.get_inputs()[0].name

    outputs = session.run(None, {input_name: input_data})

    return outputs

def draw_boxes(image, boxes, scores, classes, confidence_threshold=0.5):
    import cv2
    import numpy as np

    image_np = np.array(image)
    image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

    for box, score, class_id in zip(boxes, scores, classes):
        if score > confidence_threshold:
            x1, y1, x2, y2 = box
            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            cv2.rectangle(image_np, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label = f'Class {int(class_id)} ({score:.2f})'
            cv2.putText(image_np, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return PILImage.fromarray(cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, required=True)
    parser.add_argument('--image', type=str, required=True)
    args = parser.parse_args()

    image = PILImage.open(args.image)

    outputs = infer(args.model, image)
    output = outputs[0]

    batch = output[:, 0]
    boxes = output[:, -6:-2].clip(min=0, max=640)
    boxes /= 640
    boxes *= np.array([*image.size]*2)
    classes = output[:, -2]
    scores = output[:, -1]

    annotated_image = draw_boxes(image, boxes, scores, classes)
    annotated_image.save('output.jpg')
