from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Video
from time import perf_counter_ns

import argparse
import cv2
import os

p = argparse.ArgumentParser(description="Run video detection and tracking model.")
p.add_argument("video_path", type=str, help="Path to the video file.")
p.add_argument("--model_url", type=str, default="https://clarifai.com/pff-org/labelstudio-unified/models/video_streaming_test", help="URL of the model to use.")
p.add_argument("--deployment_id", type=str, default=None, help="Deployment ID of the model.")
p.add_argument("--output_suffix", type=str, default="_output.mp4", help="Suffix for the output video file.")
p.add_argument("--max_frames", type=int, default=None, help="Maximum number of frames to process. Default is None (process all frames).")
args = p.parse_args()

model_kwargs = {}
if args.deployment_id:
    model_kwargs['deployment_id'] = args.deployment_id

model = Model(url=args.model_url, deployment_id=args.deployment_id, deployment_user_id="pff-org")

video_path = args.video_path
if video_path.startswith('http://') or video_path.startswith('https://'):
    video = Video(url=video_path)
else:
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    video = Video(bytes=video_bytes)


tracker_params = {
    "max_dead": 100,
    "max_emb_distance": 0.0,
    "var_tracker": "manorm",
    "initialization_confidence": 0.85,
    "min_confidence": 0.51,
    "association_confidence": [0.39],
    "min_visible_frames": 0,
    "covariance_error": 100,
    "observation_error": 10,
    "max_distance": [0.5],
    "max_disappeared": 8,
    "distance_metric": "diou",
    "track_aiid": ["players"],
    "track_id_prefix": "0",
    "use_detect_box": 0,
    "project_track": 0,
    "project_fix_box_size": 0,
    "detect_box_fall_back": 0
}

start = perf_counter_ns()
result = model.predict(video=video, tracker_params=tracker_params, max_frames=args.max_frames)
end = perf_counter_ns()
print(f"Inference took {end - start} ns ({(end - start) / 1e6} ms)")

cap = cv2.VideoCapture(video_path)
frames = []
while True:
    ret, frame = cap.read()
    if not ret:
        break
    frames.append(frame)
fps = cap.get(cv2.CAP_PROP_FPS)
cap.release()
print(f"Frames: {len(result)}, 'FPS': {len(result) / (end - start) * 1e9}")

video_frames = frames

for frame_regions, video_frame in zip(result, video_frames):
    for region in frame_regions:
        x, y, xx, yy = region.box
        x1 = int(x * video_frame.shape[1])
        y1 = int(y * video_frame.shape[0])
        x2 = int(xx * video_frame.shape[1])
        y2 = int(yy * video_frame.shape[0])
        cv2.rectangle(video_frame, (x1, y1), (x2, y2), (0, 255, 0) if region.track_id else (0, 0, 255), 2)

out_path = os.path.basename(args.video_path).replace('.mp4', args.output_suffix)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
height, width = video_frames[0].shape[:2]
out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

for frame, frame_regions in zip(video_frames, result):
    out.write(frame)
out.release()