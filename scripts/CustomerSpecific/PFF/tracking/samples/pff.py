import argparse
import cv2
import json
import numpy as np
import os

from clarifai.client import Model
from clarifai.runners.utils.data_types.data_types import Image, Region
from clarifai_grpc.grpc.api.resources_pb2 import Frame
from clarifai_tracker.reid import KalmanREID
from pathlib import Path
from PIL import Image as PILImage
from tqdm import tqdm
from typing import List, Tuple

def parse_args():
    parser = argparse.ArgumentParser(description='Run object detection and tracking on video/images, save output mp4 and desired output format')
    parser.add_argument('--input', type=str, required=True, help='Path to video file or image folder')
    parser.add_argument(
        '--model_url',
        type=str,
        default='https://clarifai.com/pff-org/labelstudio-player-ref/models/player-ref-yolo',
        help='Clarifai model URL for detection'
    )
    parser.add_argument('--output-dir', type=str, default='output', help='Output directory to store the output formats')
    parser.add_argument('--max-frames', type=int, default=-1, help="Maximum number of frames to track")
    #parser.add_argument('--conf_thresh', type=float, default=0.5, help='Detection confidence threshold')
    parser.add_argument('--output-formats', nargs='+', default=['mp4', 'mot'], choices=['mp4', 'mot'])
    parser.add_argument('--detections-only', action='store_true', help='Only run detections, do not track')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bar')
    parser.add_argument('--tracker-config', type=str, default='tracker_config.json', help='Path to tracker configuration file')
    return parser.parse_args()

def load_video_or_images(input_path: str) -> Tuple[cv2.VideoCapture, int, int, int]:
    if os.path.isfile(input_path):
        cap = cv2.VideoCapture(input_path)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    else:
        image_files = sorted(Path(input_path).glob('*.jpg'))
        if not image_files:
            raise ValueError(f"No images found in {input_path}")
        sample_img = cv2.imread(str(image_files[0]))
        height, width = sample_img.shape[:2]
        fps = 30
        cap = image_files
    return cap, fps, width, height

def draw_tracks(frame: np.ndarray, tracks: List):
    for track in tracks:
        h, w, c = frame.shape

        x1, y1, x2, y2 = (np.array(track[:4]) * np.array([w, h, w, h])).astype(int)
        track_id = int(track[4])

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0) if track_id >= 0 else (255,0,0), 2)
        cv2.putText(frame, f'ID: {track_id}', (x2+10, y1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.putText(frame, f'Score: {round(track[-2], 2)}', (x2+10, y1+20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return frame

def main():
    args = parse_args()

    cap, fps, width, height = load_video_or_images(args.input)
    model = Model(args.model_url)

    # tracker_params = {
    #     "max_dead": 100,
    #     "max_emb_distance": 0.0,
    #     "var_tracker": "manorm",
    #     "initialization_confidence": 0.65,
    #     "min_confidence": 0.25,
    #     "association_confidence": [0.25],
    #     "min_visible_frames": 0,
    #     "covariance_error": 100,
    #     "observation_error": 10,
    #     "max_distance": [0.6],
    #     "max_disappeared": 8,
    #     "distance_metric": "diou",
    #     "track_aiid": ["players"],
    #     "track_id_prefix": "0",
    #     "use_detect_box": 0,
    #     "project_track": 0,
    #     "project_fix_box_size": 0,
    #     "detect_box_fall_back": 0,
    # }
    with open(args.tracker_config, 'r') as f:
        tracker_params = json.load(f)
    tracker = KalmanREID(**tracker_params)
    tracker.init_state()

    sequence_id = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = os.path.join(args.output_dir, sequence_id)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if 'mp4' in args.output_formats:
        output_mp4_name = f"{sequence_id}.mp4"
        output_mp4 = os.path.join(output_dir, output_mp4_name)
        out = cv2.VideoWriter(output_mp4, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
    else:
        out = None

    mot_tracks = []

    pbar = tqdm(disable=args.no_progress, desc='Processing frames')
    frame_idx = 0
    while True:
        if args.max_frames > 0 and frame_idx > args.max_frames:
            break
        if isinstance(cap, cv2.VideoCapture):
            ret, frame = cap.read()
            if not ret:
                break
        else:
            if frame_idx >= len(cap):
                break
            frame = cv2.imread(str(cap[frame_idx]))

        h, w = frame.shape[:2]
        regions: List[Region] = model.predict(Image.from_numpy(frame))

        cf_frame = Frame()
        for r in regions:
#            if r.concepts[0].name != 'players':
#                continue
            rp = cf_frame.data.regions.add()
            rp.CopyFrom(r.to_proto())
            rp.value = r.concepts[0].value

        if not args.detections_only:
            tracker(cf_frame.data)

        tracked_regions = [Region.from_proto(r) for r in cf_frame.data.regions]
        tracked_regions = [
            [*r.box, int(r.track_id) if r.track_id != '' else -1, r.concepts[0].value, r.concepts[0].name]
            for r in tracked_regions
        ]

        mot_tracks.extend([
            # frame id, obj_id, x, y, xx, yy, score, cls_name
            [frame_idx+1, r[4]+1, *map(float, np.array(r[:4]) * np.array([w,h,w,h])), r[-2], r[-1]]
            for r in tracked_regions
            if r[5] != -1
        ])

        if out is not None:
            frame = draw_tracks(frame, tracked_regions)
            out.write(frame)

        frame_idx += 1
        pbar.update(1)

    if isinstance(cap, cv2.VideoCapture):
        cap.release()

    if out is not None:
        out.release()

    if 'mot' in args.output_formats:
        # MOT format
        with open(os.path.join(output_dir, 'det.txt'), 'w') as f:
            for i,t in enumerate(mot_tracks):
                f.write(','.join(map(str, t)))
                f.write('\n')

#        with open(os.path.join(output_dir, 'seqinfo.ini'), 'w') as f:
#            f.write('[Sequence]\n')
#            f.write(f'name={sequence_id}\n')
#            f.write('imDir=img1\n')
#            f.write('frameRate=25\n')
#            f.write(f'seqLength={frame_idx+1}\n')
#            f.write(f'imWdith={w}\n')
#            f.write(f'imHeight={h}\n')
#            f.write('imExt=.jpg\n')

if __name__ == '__main__':
    main()
