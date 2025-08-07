import copy
import glob
import motmetrics as mm
import optuna
import os
import optuna.storages.journal
import pandas as pd

from clarifai_grpc.grpc.api.resources_pb2 import Frame, Data
from clarifai_pff.tracking.reid import KalmanREID
from functools import partial

import warnings
warnings.simplefilter('ignore', RuntimeWarning)

def obj(trial, mot_dir, gt_dir, target_class, metrics, association_threshold=0.25, reid_model_path=None):
    initial_confidence = trial.suggest_float("initialization_confidence", 0.65, 1)
    min_confidence = trial.suggest_float("min_confidence", 0.5, initial_confidence)
    max_distance = trial.suggest_float("max_distance", 0, 1)
    association_confidence = trial.suggest_float("association_confidence", 0, 1)
    max_emb_distance = trial.suggest_float("max_emb_distance", 0, 1)
    max_disappeared = trial.suggest_int("max_disappeared", 1, 30)

    tracker_params = {
        "max_dead": 100,
        "max_emb_distance": 0.0,
        "var_tracker": "manorm",
        "initialization_confidence": 0.65,
        "min_confidence": 0.25,
        "association_confidence": [0.25],
        "min_visible_frames": 0,
        "covariance_error": 100,
        "observation_error": 10,
        "max_distance": [0.6],
        "max_disappeared": 8,
        "distance_metric": "vdiou",
        "track_aiid": [target_class],
        "track_id_prefix": "",
        "use_detect_box": 0,
        "project_track": 0,
        "project_fix_box_size": 0,
        "detect_box_fall_back": 0,
    }
    
    tracker_params.update({
        "initialization_confidence": initial_confidence,
        "min_confidence": min_confidence,
        "max_distance": [max_distance],
        "association_confidence": [association_confidence],
        "max_emb_distance": max_emb_distance,
        "max_disappeared": max_disappeared,
    })
    if reid_model_path is not None:
        tracker_params["reid_model_path"] = reid_model_path

    sequences = [os.path.splitext(os.path.basename(x))[0].replace('_gt', '') for x in glob.glob(os.path.join(gt_dir, '*_gt.pb'))]
    processed_sequences = []
    all_accumulators = []
    for seq in sequences:
        gt_file = os.path.join(gt_dir, f'{seq}_gt.pb')
        det_file = os.path.join(mot_dir, f'{seq}_det.pb')

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

        if target_class is not None:
            gt = gt[gt['category'].isin([target_class])]
            det = det[det['category'].isin([target_class])]

        gt['width'] = gt['xx'] - gt['x']
        gt['height'] = gt['yy'] - gt['y']
        det['width'] = det['xx'] - det['x']
        det['height'] = det['yy'] - det['y']

        det['id'] = -1
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
        try:
            det = det[det['id'] != -1]  # remove untracked detections
        except KeyError:
            return [0.0] * len(metrics)
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
                    max_iou=1-association_threshold, # do not associate if IOU < association_threshold
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
        
    mh = mm.metrics.create()
    summary = mh.compute_many(
        all_accumulators,
        metrics=metrics, #['mota', 'motp', 'idf1', 'num_objects', 'num_matches', 'num_switches'],
        names=processed_sequences,
        generate_overall=True,
    )

    return summary.loc['OVERALL', metrics].round(3).tolist()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a simple tuning example.")
    parser.add_argument("--num_trials", type=int, default=10, help="Number of samples to run")
    parser.add_argument("target_class", type=str, help="Classes to include in evaluation")
    parser.add_argument("mot_dir", type=str, default="mot_data", help="Directory containing MOT data")
    parser.add_argument("gt_dir", type=str, default="mot_data", help="Directory containing ground truth data")
    parser.add_argument("--study-name", type=str, default="mot_tuning", help="Name of the study")
    parser.add_argument("--metrics", type=str, nargs="+", default=["idf1"], help="Metrics to optimize (space separated)")
    parser.add_argument("--association-threshold", type=float, default=0.25, help="Association threshold for IOU")
    parser.add_argument("--reid-model-path", type=str, default=None, help="Path to the reid model file")
    args = parser.parse_args()

    storage = optuna.storages.JournalStorage(optuna.storages.journal.JournalFileBackend('optuna.log'))

    study = optuna.create_study(study_name=args.study_name, directions=["maximize"]*len(args.metrics), load_if_exists=True, storage=storage)
    study.optimize(partial(obj, mot_dir=args.mot_dir, gt_dir=args.gt_dir, target_class=args.target_class, metrics=args.metrics, association_threshold=args.association_threshold, reid_model_path=args.reid_model_path), n_trials=args.num_trials)