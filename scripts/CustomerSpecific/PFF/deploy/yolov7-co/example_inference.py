import argparse
import cv2
import numpy as np
import os
from clarifai.client import Model
from clarifai.runners.utils.data_types import Image
from PIL import Image as PILImage
from time import perf_counter_ns

# parser with image option


parser = argparse.ArgumentParser(description='Run image recognition')
parser.add_argument('--image', help='Path to image file', default='/Users/sanjay/work/PFF/artifacts/player_ref/validation_per_playid/5206106_138_SL_144.jpg')
parser.add_argument('--test-latency', action='store_true')
parser.add_argument('--model', default='local')
args = parser.parse_args()

# Initialize with model URL
model = Model(url=args.model) if args.model != 'local' else Model(model_id='a', pat='a',base_url='localhost:8000')

with open(args.image, 'rb') as f:
    image_bytes = f.read()

n = 1 if not args.test_latency else 60

round_trip_ns = []
for i in range(n):
    relative = False
    start = perf_counter_ns()
    response = model.predict(
        image=Image(bytes=image_bytes),
        relative=relative
       )
    round_trip_ns.append(perf_counter_ns() - start)

    if i > 0:
        continue

    image_np = np.array(PILImage.open(args.image))
    image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    h, w, c = image_np.shape if relative else 1, 1, 1
    for region in response:
        x1,y1,x2,y2 = region.box
        class_id = region.concepts[0].name
        score = region.concepts[0].value
        x1 = int(x1 * w)
        y1 = int(y1 * h)
        x2 = int(x2 * w)
        y2 = int(y2 * h)

        cv2.rectangle(image_np, (x1, y1), (x2, y2), (0, 255, 0), 2)

        label = f'Class {class_id} ({score:.2f})'
        cv2.putText(image_np, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    os.makedirs('output', exist_ok=True)
    cv2.imwrite(os.path.join('output', os.path.basename(args.image)), image_np)

print((sum(round_trip_ns) / len(round_trip_ns))*1e-6, 'ms')
