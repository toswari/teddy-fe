import argparse
import cv2
import json
import os
import numpy as np
import pandas as pd
import scipy.linalg

from auto_homography import gen_field, field_to_pixel, transform_points, FIELD_INFOS, League, compute_camera_motion

p = argparse.ArgumentParser(description="Generate a field image with optional hash marks.")
p.add_argument("MOT_CSV")
p.add_argument("HOMOGRAPHY_JSON_DIR")
p.add_argument("FRAMES_DIR")
p.add_argument("--classes", default=['Player'], type=str, nargs='+', help="List of classes to visualize. If not provided, all classes will be visualized.")
p.add_argument('--object_ids', default=None, type=int, nargs='+', help="List of object IDs to visualize. If not provided, all objects will be visualized.")
p.add_argument('--camera_correction', action='store_true', help="Apply camera correction to the homography matrix")
args = p.parse_args()

mot_df = pd.read_csv(args.MOT_CSV, header=None, names=['frame', 'object_id', 'x', 'y', 'xx', 'yy', 'score', 'label'])

mot_df = mot_df[mot_df['label'].isin(args.classes)]

objects = mot_df['object_id'].unique()

import matplotlib.pyplot as plt

# Generate a color map for up to 25 unique objects
cmap = plt.get_cmap('tab20b', 25)
object_colors = {obj_id: tuple(int(255 * c) for c in cmap(i)[:3]) for i, obj_id in enumerate(objects)}

frame_homographies = {
    int(x.split('_')[0]): json.load(open(os.path.join(args.HOMOGRAPHY_JSON_DIR, x)))
    for x in os.listdir(args.HOMOGRAPHY_JSON_DIR) if x.endswith('.json')
}

field_info = FIELD_INFOS[League.NCAA]

field_img = gen_field(720, 1280, field_info, exclude_hash_marks=False)

prev_frame = None
prev_homography_matrix = None

for frame, group in mot_df.groupby('frame'):
    video_frame = cv2.imread(os.path.join(args.FRAMES_DIR, f'{frame:04d}.jpg'))
    
    if frame not in frame_homographies and not args.camera_correction:
        # If no homography is available and camera correction is not requested, skip this frame
        print(f"Skipping frame {frame} as no homography is available and camera correction is not requested.")
        combined = np.hstack((video_frame, field_img))
        cv2.imwrite(f'output_frame_{frame}.jpg', combined)
        continue
    elif frame not in frame_homographies and args.camera_correction:
        # if prev_homography_matrix is None or not args.camera_correction:
        #     combined = np.hstack((video_frame, field_img))
        #     cv2.imwrite(f'output_frame_{frame}.jpg', combined)
        #     continue
        camera_motion = compute_camera_motion(prev_frame, video_frame)
        homography_matrix = prev_homography_matrix @ np.linalg.inv(camera_motion)
    else:
        homography = frame_homographies[frame]
        homography_matrix = np.array(homography['matrix'])

        if prev_frame is not None and prev_homography_matrix is not None and args.camera_correction:
            camera_motion = compute_camera_motion(prev_frame, video_frame)
            hyp_homography_matrix = prev_homography_matrix @ np.linalg.inv(camera_motion)

            lie_dist = np.linalg.norm(scipy.linalg.logm(homography_matrix) - scipy.linalg.logm(hyp_homography_matrix))
            print(f"Frame {frame}: Lie distance = {lie_dist}")
            if lie_dist > 15:
                homography_matrix = hyp_homography_matrix
    
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
        cv2.circle(field_img, field_to_pixel(*transformed_pt, field_img, field_info), 5, color, -1)

    combined = np.hstack((video_frame, field_img))
    cv2.imwrite(f'output_frame_{frame}.jpg', combined)