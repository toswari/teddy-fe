import argparse
import cv2
import json
import os
import numpy as np
import pandas as pd
import scipy.linalg

from clarifai_grpc.grpc.api.resources_pb2 import Frame
from clarifai_pff.tracking.reid import KalmanREID

import warnings
warnings.simplefilter('ignore', RuntimeWarning)

from clarifai_pff.auto_homography import gen_field, field_to_pixel, transform_points, FIELD_INFOS, League, compute_camera_motion

p = argparse.ArgumentParser(description="Generate a field image with optional hash marks.")
p.add_argument("MOT_CSV")
p.add_argument("HOMOGRAPHY_JSON_DIR")
p.add_argument("FRAMES_DIR")
p.add_argument("--classes", default=['Player'], type=str, nargs='+', help="List of classes to visualize. If not provided, all classes will be visualized.")
p.add_argument('--object_ids', default=None, type=int, nargs='+', help="List of object IDs to visualize. If not provided, all objects will be visualized.")
p.add_argument('--camera_correction', action='store_true', help="Apply camera correction to the homography matrix")
# p.add_argument('--no-tracks', action='store_true', help="Do not draw tracks on the field image")
# p.add_argument('--include_homography', action='store_true', help="Include homography in the output frames")
p.add_argument('--tracker_config', type=str, default=None, help='Path to tracker configuration file, if re-tracking is needed')
p.add_argument('--embeddings', action='store_true', help='Use embeddings for tracking')
args = p.parse_args()

mot_df = pd.read_csv(args.MOT_CSV, header=None, names=['frame', 'object_id', 'x', 'y', 'xx', 'yy', 'score', 'label'])

mot_df = mot_df[mot_df['label'].isin(args.classes)]

if args.tracker_config is not None:
    mot_df['object_id'] = -1
    with open(args.tracker_config, 'r') as f:
        tracker_params = json.load(f)
    # run tracker
    tracker = KalmanREID(
        **tracker_params,
    )
    tracker.init_state()
    new_dfs = []
    for frame, group in mot_df.groupby('frame'):
        video_frame = cv2.imread(os.path.join(args.FRAMES_DIR, f'{frame:04d}.jpg'))

        cf_frame = Frame()
        for _, row in group.iterrows():
            r = cf_frame.data.regions.add()
            r.region_info.bounding_box.left_col = row['x'] / 1280
            r.region_info.bounding_box.top_row = row['y'] / 720
            r.region_info.bounding_box.right_col = row['xx'] / 1280
            r.region_info.bounding_box.bottom_row = row['yy'] / 720
            r.value = row['score']
            r.data.concepts.add(name=row['label'], value=r.value)
            if args.embeddings:
                crop = video_frame[int(row['y']):int(row['yy']), int(row['x']):int(row['xx'])]
                embedding = crop.mean(axis=(0, 1)).flatten()  # Simple mean embedding
                emb = r.data.embeddings.add()
                emb.vector.extend(embedding)
        tracker(cf_frame.data)
        new_dfs.append(
            pd.DataFrame.from_records(
                [
                    {
                        'frame': frame,
                        'object_id': int(region.track_id) if region.track_id != '' else -1,
                        'x': region.region_info.bounding_box.left_col * 1280,
                        'y': region.region_info.bounding_box.top_row * 720,
                        'xx': region.region_info.bounding_box.right_col * 1280,
                        'yy': region.region_info.bounding_box.bottom_row * 720,
                        'score': region.value,
                        'label': region.data.concepts[0].name if region.data.concepts else ''
                    } 
                for region in cf_frame.data.regions if region.track_id != ''
                ]
            )
        )
    #     if len(group) != len(cf_frame.data.regions):
    #         breakpoint()
    #     for (i,row), region in zip(group.iterrows(), cf_frame.data.regions):
    #         mot_df.loc[i, 'object_id'] = int(region.track_id) if region.track_id != '' else -1
    mot_df = pd.concat(new_dfs, ignore_index=True)
    mot_df = mot_df[mot_df['object_id'] != -1]  # remove untracked detections

objects = mot_df['object_id'].unique()

import matplotlib.pyplot as plt
import itertools

# Generate a color map for up to 25 unique objects
cmap = list(itertools.chain(plt.get_cmap('tab20b').colors, plt.get_cmap('tab20c').colors))
object_colors = {obj_id: tuple(int(255 * c) for c in cmap[i][:3]) for i, obj_id in enumerate(objects)}

frame_homographies = {
    int(x.split('_')[0]): json.load(open(os.path.join(args.HOMOGRAPHY_JSON_DIR, x)))
    for x in os.listdir(args.HOMOGRAPHY_JSON_DIR) if x.endswith('.json')
}

field_info = FIELD_INFOS[League.NCAA]

field_img = gen_field(720, 1280, field_info, exclude_hash_marks=False)

prev_frame = None
prev_homography_matrix = None

image_points = None
field_points = None

for frame, group in mot_df.groupby('frame'):
    # if args.no_tracks:
    field_img_no_tracks = gen_field(720, 1280, field_info, exclude_hash_marks=False)

    hom_img = gen_field(720, 1280, field_info, exclude_hash_marks=True)

    video_frame = cv2.imread(os.path.join(args.FRAMES_DIR, f'{frame:04d}.jpg'))
    
    if frame not in frame_homographies and not args.camera_correction:
        # If no homography is available and camera correction is not requested, skip this frame
        print(f"Skipping frame {frame} as no homography is available and camera correction is not requested.")
        combined = np.vstack((np.hstack((video_frame, hom_img)), np.hstack((field_img_no_tracks, field_img))))
        cv2.imwrite(f'output_frame_{frame}.jpg', combined)
        continue
    elif frame not in frame_homographies and args.camera_correction:
        # if prev_homography_matrix is None or not args.camera_correction:
        #     combined = np.hstack((video_frame, field_img))
        #     cv2.imwrite(f'output_frame_{frame}.jpg', combined)
        #     continue
        camera_motion = compute_camera_motion(prev_frame, video_frame)
        homography_matrix = prev_homography_matrix @ np.linalg.inv(camera_motion)

        image_points = transform_points(field_points, homography_matrix, inverse=True) if field_points is not None else None
        # image_points = transform_points(image_points, camera_motion) if image_points is not None else None
        # field_points = transform_points(field_points, camera_motion, inverse=True) if field_points is not None else None
    else:
        homography = frame_homographies[frame]
        homography_matrix = np.array(homography['matrix'])
        image_points = np.array(homography['image_points'])
        field_points = np.array(homography['field_points'])

        if prev_frame is not None and prev_homography_matrix is not None and args.camera_correction:
            camera_motion = compute_camera_motion(prev_frame, video_frame)
            hyp_homography_matrix = prev_homography_matrix @ np.linalg.inv(camera_motion)

            lie_dist = np.linalg.norm(scipy.linalg.logm(homography_matrix) - scipy.linalg.logm(hyp_homography_matrix))
            print(f"Frame {frame}: Lie distance = {lie_dist}")
            if lie_dist > 15:
                homography_matrix = hyp_homography_matrix

    for pt in image_points:
        cv2.circle(video_frame, (int(pt[0]), int(pt[1])), 5, (255, 0, 0), -1)

    for pt in field_points:
        cv2.circle(hom_img, field_to_pixel(*pt, hom_img, field_info), 5, (0, 255, 0), -1)

    fov_points = np.array([[0,0], [video_frame.shape[1], 0], [video_frame.shape[1], video_frame.shape[0]], [0, video_frame.shape[0]]])
    fov_points_transformed = np.array([field_to_pixel(*pt, hom_img, field_info) for pt in transform_points(fov_points, homography_matrix)]).astype(int)
    cv2.polylines(hom_img, [np.int32(fov_points_transformed)], isClosed=True, color=(0, 255, 0), thickness=2)
    
    prev_frame = video_frame.copy()
    prev_homography_matrix = homography_matrix

    group = group[group['object_id'].isin(args.object_ids)] if args.object_ids else group
    
    for _, row in group.iterrows():
        color = object_colors.get(row['object_id'], (255, 0, 0))
        cv2.rectangle(video_frame, (int(row['x']), int(row['y'])), (int(row['xx']), int(row['yy'])), color, 2)

    # for _, row in group.iterrows():
        # x, y = row['x'], row['y']
        # # Apply homography transformation
        # take middle of bottom of box
        pt = (row['x'] + row['xx']) / 2, row['yy']

        transformed_pt = transform_points(np.array([[pt]]), homography_matrix)[0]
        color = object_colors.get(row['object_id'], (255, 0, 0))
        cv2.circle(field_img, field_to_pixel(*transformed_pt, field_img, field_info), 2, color, -1)
        cv2.putText(
            field_img_no_tracks,
            str(row['object_id']),
            field_to_pixel(*transformed_pt, field_img_no_tracks, field_info),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA
        )

    combined = np.vstack((np.hstack((video_frame, hom_img)), np.hstack((field_img_no_tracks, field_img))))
    cv2.imwrite(f'output_frame_{frame:04d}.jpg', combined)