import argparse
import cv2
import json
import os
import numpy as np
import pandas as pd
import scipy.linalg

from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from clarifai_pff.tracking.reid import KalmanREID

import warnings
warnings.simplefilter('ignore', RuntimeWarning)

from clarifai_pff.auto_homography import gen_field, field_to_pixel, transform_points, FIELD_INFOS, League, compute_camera_motion

p = argparse.ArgumentParser(description="Generate a field image with optional hash marks.")
p.add_argument("MOT_PB")
p.add_argument("HOMOGRAPHY_JSON_DIR")
p.add_argument("FRAMES_DIR")
p.add_argument("--classes", default=['players'], type=str, nargs='+', help="List of classes to visualize. If not provided, all classes will be visualized.")
p.add_argument('--object_ids', default=None, type=int, nargs='+', help="List of object IDs to visualize. If not provided, all objects will be visualized.")
p.add_argument('--camera_correction', action='store_true', help="Apply camera correction to the homography matrix")
# p.add_argument('--no-tracks', action='store_true', help="Do not draw tracks on the field image")
# p.add_argument('--include_homography', action='store_true', help="Include homography in the output frames")
p.add_argument('--tracker_config', type=str, default=None, help='Path to tracker configuration file, if re-tracking is needed')
p.add_argument('--max_frames', type=int, default=None, help='Maximum number of frames to process (for testing purposes)')
p.add_argument('--smooth', action='store_true', help='Apply B-spline smoothing to the object traces')
args = p.parse_args()

# mot_df = pd.read_csv(args.MOT_CSV, header=None, names=['frame', 'object_id', 'x', 'y', 'xx', 'yy', 'score', 'label'])
with open(args.MOT_PB, 'rb') as f:
    mot_data = Data.FromString(f.read())

mot_df = pd.DataFrame.from_records(
    [
        {
            'frame': i,
            'object_id': int(region.track_id) if region.track_id != '' else -1,
            'x': region.region_info.bounding_box.left_col * 1280,
            'y': region.region_info.bounding_box.top_row * 720,
            'xx': region.region_info.bounding_box.right_col * 1280,
            'yy': region.region_info.bounding_box.bottom_row * 720,
            'score': region.value,
            'label': region.data.concepts[0].name if region.data.concepts else ''
        } for i, frame in enumerate(mot_data.frames, 1) for region in frame.data.regions
    ]
)

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
    for frame_idx, frame in enumerate(mot_data.frames, 1):
        video_frame = cv2.imread(os.path.join(args.FRAMES_DIR, f'{frame_idx:04d}.jpg'))
        tracker(frame.data)
        new_dfs.append(
            pd.DataFrame.from_records(
                [
                    {
                        'frame': frame_idx,
                        'object_id': int(region.track_id) if region.track_id != '' else -1,
                        'x': region.region_info.bounding_box.left_col * 1280,
                        'y': region.region_info.bounding_box.top_row * 720,
                        'xx': region.region_info.bounding_box.right_col * 1280,
                        'yy': region.region_info.bounding_box.bottom_row * 720,
                        'score': region.value,
                        'label': region.data.concepts[0].name if region.data.concepts else ''
                    } 
                for region in frame.data.regions if region.track_id != ''
                ]
            )
        )
    #     if len(group) != len(cf_frame.data.regions):
    #         breakpoint()
    #     for (i,row), region in zip(group.iterrows(), cf_frame.data.regions):
    #         mot_df.loc[i, 'object_id'] = int(region.track_id) if region.track_id != '' else -1
    mot_df = pd.concat(new_dfs, ignore_index=True)
    # mot_df = mot_df[mot_df['object_id'] != -1]  # remove untracked detections

objects = mot_df['object_id'].unique()

import matplotlib.pyplot as plt
import itertools
from scipy.interpolate import make_splprep, splev
from scipy.interpolate import interp1d

# Generate a color map for up to 25 unique objects
cmap = list(itertools.chain(plt.get_cmap('tab20b').colors, plt.get_cmap('tab20c').colors))
object_colors = {obj_id: tuple(int(255 * c) for c in cmap[i][:3]) for i, obj_id in enumerate(objects)}
object_colors[-1] = (0,0,255)

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

object_traces = {obj_id: [] for obj_id in objects}

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
            if lie_dist > 5: #15:
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

        # # Apply homography transformation
        # take middle of bottom of box
        pt = (row['x'] + row['xx']) / 2, row['yy']

        transformed_pt = transform_points(np.array([[pt]]), homography_matrix)[0]

        object_traces[row['object_id']].append(transformed_pt)

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

    if args.smooth and (frame == mot_df['frame'].max() or (args.max_frames is not None and frame == args.max_frames)):
        # Fit B-splines to object traces
        # TODO(rizzi): fix smoothing parameter formula (diff(y) is occasionally to aggressive)
        # field_img = gen_field(720, 1280, field_info, exclude_hash_marks=False)
        for obj_id, trace in object_traces.items():
            if len(trace) > 3:  # Need at least 4 points for cubic spline
                # Convert trace to numpy array and transpose for splprep
                trace_array = np.array(trace)
                x = trace_array[:, 0]
                y = trace_array[:, 1]
                
                # Create parameter array (time)
                t = np.arange(len(trace))

                # Compute upper envelope of y signal

                # Find local maxima for upper envelope
                def find_upper_envelope(t, y):
                    # Find local maxima
                    maxima_indices = []
                    maxima_indices.append(0)  # Include first point
                    
                    for i in range(1, len(y)-1):
                        if y[i] >= y[i-1] and y[i] >= y[i+1]:
                            maxima_indices.append(i)
                    
                    maxima_indices.append(len(y)-1)  # Include last point
                    
                    # Extract maxima points
                    t_maxima = t[maxima_indices]
                    y_maxima = y[maxima_indices]
                    
                    # Interpolate upper envelope
                    if len(t_maxima) > 1:
                        envelope_func = interp1d(t_maxima, y_maxima, kind='linear', 
                                               bounds_error=False, fill_value='extrapolate')
                        y_envelope = envelope_func(t)
                    else:
                        y_envelope = np.full_like(y, y_maxima[0])
                    
                    return y_envelope

                y_upper_envelope = find_upper_envelope(t, y)
                
                # Calculate variance in x and y coordinates to determine smoothing parameter
                var_y = np.var(np.diff(y))
                total_variance = var_y
                print(f"Object {obj_id}: Variance in y = {var_y}, Total Variance = {total_variance}")
                # Scale smoothing parameter based on variance (higher variance = more smoothing)
                # s = 500 * total_variance # 55
                s = 20
                
                # Fit B-spline
                spl, u = make_splprep([x, y_upper_envelope], u=t, s=s, k=min(3, len(trace)-1))
                
                # Generate smooth curve
                u_new = np.linspace(0, len(trace)-1, len(trace)*5)
                x_smooth, y_smooth = spl(u_new)

                # Draw smooth trajectory on field image
                color = object_colors.get(obj_id, (255, 0, 0))
                for i in range(len(x_smooth)-1):
                    pt1 = x_smooth[i], y_smooth[i]
                    pt2 = x_smooth[i+1], y_smooth[i+1]
                    cv2.line(field_img, 
                            field_to_pixel(*pt1, field_img, field_info),
                            field_to_pixel(*pt2, field_img, field_info),
                            color, 2)

    combined = np.vstack((np.hstack((video_frame, hom_img)), np.hstack((field_img_no_tracks, field_img))))
    cv2.imwrite(f'output_frame_{frame:04d}.jpg', combined)

    if args.max_frames is not None and frame == args.max_frames:
        break