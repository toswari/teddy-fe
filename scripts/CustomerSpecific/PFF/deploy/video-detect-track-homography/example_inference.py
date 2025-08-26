from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Video
from time import perf_counter_ns

import argparse
import cv2
import json
import os

p = argparse.ArgumentParser(description="Run video detection and tracking model.")
p.add_argument("video_path", type=str, help="Path to the video file.")
p.add_argument("--model_url", type=str, default="https://clarifai.com/pff-org/labelstudio-unified/models/video-entire-pipeline-gpu2", help="URL of the model to use.")
p.add_argument("--deployment_id", type=str, default=None, help="Deployment ID of the model.")
p.add_argument("--output_suffix", type=str, default="_output.mp4", help="Suffix for the output video file.")
p.add_argument("--max_frames", type=int, default=None, help="Maximum number of frames to process. Default is None (process all frames).")
p.add_argument("--tracker_config", type=str, default=None, help="Path to a JSON file with tracker parameters. If not provided, tracking is disabled.")
p.add_argument("--out_dir", type=str, default=os.getcwd(), help="Directory to save the output video and result file. Default is current working directory.")
p.add_argument("--output_formats", nargs='+', default=['pb', 'mp4'], choices=['pb', 'mp4'], help="Output formats to save the results. Default is ['pb', 'mp4'].")
args = p.parse_args()

model_kwargs = {}
if args.deployment_id:
    model_kwargs['deployment_id'] = args.deployment_id

model = Model(url=args.model_url, deployment_id=args.deployment_id, deployment_user_id="pff-org")

video_path = args.video_path
if video_path.startswith('http://') or video_path.startswith('https://'):
    # assuming s3 presigned url
    video_id = video_path.split('.mp4')[0].split('/')[-1]
    video = Video(url=video_path)
else:
    video_id = os.path.basename(args.video_path).replace('.mp4', '')
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
if not args.tracker_config:
    tracker_params = tracker_params
else:
    with open(args.tracker_config, 'r') as f:
        tracker_params = json.load(f)

start = perf_counter_ns()
result = model.predict(video=video, tracker_params=tracker_params, max_frames=args.max_frames)
end = perf_counter_ns()
print(f"Inference took {end - start} ns ({(end - start) / 1e6} ms)")

# from google.protobuf.json_format import MessageToDict
# import json

# # Add this code after getting the result and before the exception
# # Convert first frame result to dictionary
# first_frame_dict = MessageToDict(result[0].proto)

# # Store in JSON file
# output_json_path = os.path.join(args.out_dir, f'{video_id}_first_frame.json')
# with open(output_json_path, 'w') as f:
#     json.dump(first_frame_dict, f, indent=2)

print(result[0].proto)
