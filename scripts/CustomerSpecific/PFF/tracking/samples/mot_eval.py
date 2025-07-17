import motmetrics as mm
import numpy as np
import os
import pandas as pd
from tqdm import tqdm

if __name__ == '__main__':
    import argparse

    p = argparse.ArgumentParser(description='Evaluate MOT results using MOT metrics.')
    p.add_argument('dataset_folder', type=str, help='folder containing gt and det files. Seq_id/[det|gt].txt where det/gt.txt are frame, id, x, y, xx, yy, conf, category')
    p.add_argument('--assoc_threshold', type=float, default=0.25, help='Association threshold for IoU (default: 0.25)')
    p.add_argument('--include_classes', nargs='+', default=None, help='List of classes to include in evaluation (default: all classes)')
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

    sequences = os.listdir(args.dataset_folder)
    assoc_threshold = args.assoc_threshold

    processed_sequences = []
    all_accumulators = []
    hota_summaries = []
    for seq in tqdm(sequences, desc='Processing sequences'):
        gt_file = os.path.join(args.dataset_folder, seq, 'gt.txt')
        det_file = os.path.join(args.dataset_folder, seq, 'det.txt')

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

        if args.include_classes is not None:
            gt = gt[gt['category'].isin(args.include_classes)]
            det = det[det['category'].isin(args.include_classes)]

        gt['width'] = gt['xx'] - gt['x']
        gt['height'] = gt['yy'] - gt['y']
        det['width'] = det['xx'] - det['x']
        det['height'] = det['yy'] - det['y']

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
