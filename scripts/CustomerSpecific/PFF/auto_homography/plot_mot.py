import argparse
import cv2
import json
import os
import numpy as np
import pandas as pd

from auto_homography import gen_field, field_to_pixel, transform_points, FIELD_INFOS, League

p = argparse.ArgumentParser(description="Generate a field image with optional hash marks.")
p.add_argument("MOT_CSV")
p.add_argument("HOMOGRAPHY_JSON_DIR")
p.add_argument("FRAMES_DIR")
p.add_argument('--object_id', default=None, type=int)
args = p.parse_args()

mot_df = pd.read_csv(args.MOT_CSV, header=None, names=['frame', 'object_id', 'x', 'y', 'xx', 'yy', 'score', 'label'])

mot_df = mot_df[mot_df['label'].isin(['players'])]
if args.object_id is not None:
    mot_df = mot_df[mot_df['object_id'] == args.object_id]

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

field_img = gen_field(720, 1280, field_info, exclude_hash_marks=True)

for frame, group in mot_df.groupby('frame'):
    video_frame = cv2.imread(os.path.join(args.FRAMES_DIR, f'{frame:04d}.jpg'))
    for _, row in group.iterrows():
        color = object_colors.get(row['object_id'], (255, 0, 0))
        cv2.rectangle(video_frame, (int(row['x']), int(row['y'])), (int(row['xx']), int(row['yy'])), color, 2)
    
    if frame not in frame_homographies:
        combined = np.hstack((video_frame, field_img))
        cv2.imwrite(f'output_frame_{frame}.jpg', combined)
        continue
    
    homography = frame_homographies[frame]
    m = np.array(homography['matrix'])
    
    for _, row in group.iterrows():
        # x, y = row['x'], row['y']
        # # Apply homography transformation
        # take middle of bottom of box
        pt = (row['x'] + row['xx']) / 2, row['yy']

        transformed_pt = transform_points(np.array([[pt]]), m)[0]
        color = object_colors.get(row['object_id'], (255, 0, 0))
        cv2.circle(field_img, field_to_pixel(*transformed_pt, field_img, field_info), 5, color, -1)

    combined = np.hstack((video_frame, field_img))
    cv2.imwrite(f'output_frame_{frame}.jpg', combined)