import copy
import glob
import motmetrics as mm
import optuna
import os
import optuna.storages.journal
import pandas as pd

from clarifai_grpc.grpc.api.resources_pb2 import Frame
from clarifai_tracker.reid import KalmanREID
from functools import partial

def obj(trial, mot_dir, target_class, metrics, association_threshold=0.25):
    initial_confidence = trial.suggest_float("initialization_confidence", 0.65, 1)
    min_confidence = trial.suggest_float("min_confidence", 0.5, initial_confidence)
    max_distance = trial.suggest_float("max_distance", 0, 1)
    association_confidence = trial.suggest_float("association_confidence", 0, 1)

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
        "distance_metric": "diou",
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
    })

    sequences = os.listdir(mot_dir)
    processed_sequences = []
    all_accumulators = []
    for seq in sequences:
        gt_file = os.path.join(mot_dir, seq, 'gt.txt')
        det_file = os.path.join(mot_dir, seq, 'det.txt')

        if not os.path.exists(gt_file) or not os.path.exists(det_file):
            print(f"Skipping {seq}: missing gt or det file.")
            continue
        processed_sequences.append(seq)

        # Load ground truth and detections
        gt = pd.read_csv(gt_file, sep=',', header=None, names=['frame', 'id', 'x', 'y', 'xx', 'yy', 'conf', 'category'])
        det = pd.read_csv(det_file, sep=',', header=None, names=['frame', 'id', 'x', 'y', 'xx', 'yy', 'conf', 'category'])

        gt_cats, det_cats = gt.category.unique(), det.category.unique()
        if set(gt_cats) != set(det_cats):
            print(f"Warning: Categories in ground truth and detections do not match for sequence {seq}.")
            print(f"Ground truth categories: {gt_cats}")
            print(f"Detection categories: {det_cats}")

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
        for frame, group in det.groupby('frame'):
            cf_frame = Frame()
            for _, row in group.iterrows():
                r = cf_frame.data.regions.add()
                r.region_info.bounding_box.left_col = row['x'] / 1280
                r.region_info.bounding_box.top_row = row['y'] / 720
                r.region_info.bounding_box.right_col = row['xx'] / 1280
                r.region_info.bounding_box.bottom_row = row['yy'] / 720
                r.value = row['conf']
                r.data.concepts.add(name=row['category'], value=r.value)
            tracker(cf_frame.data)
            for (i,row), region in zip(group.iterrows(), cf_frame.data.regions):
                det.loc[i, 'id'] = int(region.track_id) if region.track_id != '' else -1

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
    parser.add_argument("--study-name", type=str, default="mot_tuning", help="Name of the study")
    parser.add_argument("--metrics", type=str, nargs="+", default=["idf1"], help="Metrics to optimize (space separated)")
    args = parser.parse_args()

    storage = optuna.storages.JournalStorage(optuna.storages.journal.JournalFileBackend('optuna.log'))

    study = optuna.create_study(study_name=args.study_name, directions=["maximize"]*len(args.metrics), load_if_exists=True, storage=storage)
    study.optimize(partial(obj, mot_dir=args.mot_dir, target_class=args.target_class, metrics=args.metrics), n_trials=args.num_trials)