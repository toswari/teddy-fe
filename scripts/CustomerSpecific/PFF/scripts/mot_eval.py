import glob
import json
import motmetrics as mm
import numpy as np
import os
import pandas as pd

from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from clarifai_pff.tracking.reid import KalmanREID
from tqdm import tqdm

import warnings
warnings.simplefilter('ignore', RuntimeWarning)

if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser(description='Evaluate MOT results using MOT metrics.')
    p.add_argument('dataset_folder', type=str, help='folder containing gt and det files. Seq_id_{det,gt}.pb')
    p.add_argument('--assoc_threshold', type=float, default=0.25, help='Association threshold for IoU (default: 0.25)')
    p.add_argument('--include_classes', nargs='+', default=None, help='List of classes to include in evaluation (default: all classes)')
    # p.add_argument('--det-file', type=str, default='det.txt', help='Name of the detection file (default: det.txt)')
    p.add_argument('--tracker-config', type=str, default=None, help='Path to tracker configuration file, if re-tracking is needed')
    args = p.parse_args()

    metrics = ['num_frames',
                 'mota',
                 'motp',
                 'precision',
                 'recall',
                 'idf1',
                 'num_fragmentations',
                 'num_switches',
                 'num_false_positives',
                 'num_misses',
                 'mostly_tracked',
                 'partially_tracked',
                 'num_unique_objects',
                 ]

    sequences = [os.path.splitext(os.path.basename(x))[0].replace('_gt', '') for x in glob.glob(os.path.join(args.dataset_folder, '*_gt.pb'))]
    assoc_threshold = args.assoc_threshold

    processed_sequences = []
    all_accumulators = []
    hota_summaries = []
    for seq in tqdm(sequences, desc='Processing sequences'):
        gt_file = os.path.join(args.dataset_folder, f'{seq}_gt.pb')
        det_file = os.path.join(args.dataset_folder, f'{seq}_det.pb')

        if not os.path.exists(gt_file) or not os.path.exists(det_file):
            print(f"Skipping {seq}: missing gt or det file.")
            continue
        processed_sequences.append(seq)

        # Load ground truth and detections
        with open(gt_file, 'rb') as f:
            gt_data = Data.FromString(f.read())
        with open(det_file, 'rb') as f:
            det_data = Data.FromString(f.read())

        h, w = gt_data.frames[0].data.image.image_info.height, gt_data.frames[0].data.image.image_info.width

        gt_cats, det_cats = set((r.data.concepts[0].name for f in gt_data.frames for r in f.data.regions)), set((r.data.concepts[0].name for f in det_data.frames for r in f.data.regions))
        if set(gt_cats) != set(det_cats):
            print(f"Warning: Categories in ground truth and detections do not match for sequence {seq}.")
            print(f"Ground truth categories: {gt_cats}")
            print(f"Detection categories: {det_cats}")

        gt = []
        det = []
        for fi, f in enumerate(gt_data.frames):
            for r in f.data.regions:
                gt.append({
                    'frame': fi + 1,  # MOT frames are 1-indexed
                    'id': int(r.track_id) if r.track_id else -1,  # Use -1 for untracked regions
                    'x': r.region_info.bounding_box.left_col * w,
                    'y': r.region_info.bounding_box.top_row * h,
                    'xx': r.region_info.bounding_box.right_col * w,
                    'yy': r.region_info.bounding_box.bottom_row * h,
                    'conf': r.value,
                    'category': r.data.concepts[0].name
                })
        for fi, f in enumerate(det_data.frames):
            for r in f.data.regions:
                det.append({
                    'frame': fi + 1,  # MOT frames are 1-indexed
                    'id': int(r.track_id) if r.track_id else -1,  # Use -1 for untracked regions
                    'x': r.region_info.bounding_box.left_col * w,
                    'y': r.region_info.bounding_box.top_row * h,
                    'xx': r.region_info.bounding_box.right_col * w,
                    'yy': r.region_info.bounding_box.bottom_row * h,
                    'conf': r.value,
                    'category': r.data.concepts[0].name
                })
        
        gt = pd.DataFrame.from_records(gt)
        det = pd.DataFrame.from_records(det)

        if args.include_classes is not None:
            gt = gt[gt['category'].isin(args.include_classes)]
            det = det[det['category'].isin(args.include_classes)]

        gt['width'] = gt['xx'] - gt['x']
        gt['height'] = gt['yy'] - gt['y']
        det['width'] = det['xx'] - det['x']
        det['height'] = det['yy'] - det['y']

        if args.tracker_config is not None:
            det['id'] = -1
            with open(args.tracker_config, 'r') as f:
                tracker_params = json.load(f)
            # run tracker
            tracker = KalmanREID(
                **tracker_params,
            )
            tracker.init_state()
            new_dets = []
            for frame_idx, frame in enumerate(det_data.frames, 1):
                for region in frame.data.regions:
                    region.track_id = ''
                tracker(frame.data)
                new_dets.append(
                    pd.DataFrame.from_records(
                        [
                            {
                                'frame': frame_idx,
                                'id': int(region.track_id) if region.track_id != '' else -1,
                                'x': region.region_info.bounding_box.left_col * w,
                                'y': region.region_info.bounding_box.top_row * h,
                                'xx': region.region_info.bounding_box.right_col * w,
                                'yy': region.region_info.bounding_box.bottom_row * h,
                                'conf': region.value,
                                'category': region.data.concepts[0].name if region.data.concepts else ''
                            } 
                        for region in frame.data.regions if region.track_id != ''
                        ]
                    )
                )
            det = pd.concat(new_dets, ignore_index=True)
            det = det[det['id'] != -1]  # remove untracked detections
            det[['width', 'height']] = det[['xx', 'yy']].to_numpy() - det[['x', 'y']].to_numpy()

        # Create accumulator
        acc = mm.MOTAccumulator(auto_id=True)
        all_accumulators.append(acc)

        min_frame = max(gt['frame'].min(), det['frame'].min())
        max_frame = min(gt['frame'].max(), det['frame'].max())
        for frame in range(min_frame, max_frame):
            gt_frame = gt[gt['frame'] == frame]
            det_frame = det[det['frame'] == frame]

            # Prepare ground truth and detections
            gt_ids = gt_frame['id'].values
            det_ids = det_frame['id'].values

            iou_dist = mm.distances.iou_matrix(
                    gt_frame[['x', 'y', 'width', 'height']].to_numpy(),
                    det_frame[['x', 'y', 'width', 'height']].to_numpy(),
                    max_iou=1-assoc_threshold, # do not associate if IOU < 0.6
                )

            #if not (iou_dist.shape == (len(gt_ids), len(det_ids))):
            #    breakpoint()
            #assert iou_dist.shape == (len(gt_ids), len(det_ids)), f"IOU matrix shape mismatch, {frame} {iou_dist.shape} != {len(gt_ids)} x {len(det_ids)}"

            # Add to accumulator
            acc.update(
                gt_ids,
                det_ids,
                iou_dist,
            )

        # Compute metrics
        mh = mm.metrics.create()
        summary = mh.compute(acc, metrics=metrics, name=seq)

        # hota
        hota_res_list = mm.utils.compare_to_groundtruth_reweighting(
            gt.rename(columns={'frame': 'FrameId', 'id': 'Id'}).set_index(['FrameId', 'Id']),
            det.rename(columns={'frame': 'FrameId', 'id': 'Id'}).set_index(['FrameId', 'Id']),
            'iou',
            distfields=['x', 'y', 'width', 'height'],
            distth=np.arange(0.05,.99,0.05),)
        mh = mm.metrics.create()
        hota_summary = mh.compute_many(hota_res_list,
                                       metrics=['assa_alpha', 'deta_alpha', 'hota_alpha'],
                                       generate_overall=True).loc['OVERALL']
        hota_summary.name = seq
        hota_summaries.append(hota_summary)

    mh = mm.metrics.create()
    summary = mh.compute_many(
        all_accumulators,
        metrics=metrics,
        names=processed_sequences,
        generate_overall=True
    )
    full_summary = pd.DataFrame(hota_summaries).join(summary, how='outer').round(2)
    print(full_summary.to_markdown())
    full_summary.to_csv('mot-metrics.csv')
    with open('mot-metrics.md', 'w') as f:
        f.write(full_summary.to_markdown())
