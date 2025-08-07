import argparse
import itertools
import os

import numpy as np
import torch
from joblib import dump
from scipy.optimize import linear_sum_assignment
# from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from torchvision.ops import box_iou

from clarifai_grpc.grpc.api.resources_pb2 import Data
from clarifai_pff.tracking.distance_utils import distances


def check_db_path(db_file):
  """
    get pb files only
    """
  _, file_extension = os.path.splitext(db_file)
  return file_extension == ".pb"


def create_dbs_list(dbs_root_path):
  dbs_paths = sorted(os.listdir(dbs_root_path))
  return [os.path.join(dbs_root_path, fn) for fn in dbs_paths if check_db_path(fn)]


def load_databatches(dbs_root_path):
  db_path_list = create_dbs_list(dbs_root_path)

  db_list = []

  for filename in db_path_list:
    with open(filename, 'rb') as f:
      db = Data.FromString(f.read())
    db_list.append(db)

  return db_list, db_path_list


def match_regions(gt, pred, iou_threshold=0.5):
  """
    Function will extract features per predicted box and labels as to if
    each example is a True or False Positive
    Function operates on a single frame
    """

  # Get bounding boxes and labels
  bboxes = []
  labels = []
  for ex in [gt, pred]:
    ex_labels = []
    boxes = torch.zeros(len(ex.regions), 4)
    for idx, region in enumerate(ex.regions):
      bbox = region.region_info.bounding_box
      boxes[idx, 0] = bbox.left_col
      boxes[idx, 2] = bbox.right_col
      boxes[idx, 1] = bbox.top_row
      boxes[idx, 3] = bbox.bottom_row
      region_labels = []
      for tag in region.data.concepts:
        region_labels.append(tag.name)
      ex_labels.append((idx, region_labels))
    bboxes.append(boxes)
    labels.append(ex_labels)

  # Calculate bounding box distance
  iou_overlap = box_iou(bboxes[0], bboxes[1])
  distances = 1 - iou_overlap

  # Compare labels and add to distance if no labels match
  for (gt_ind, gt_labels), (pred_ind, pred_labels) in itertools.product(*labels):
    if not len(set(gt_labels).intersection(set(pred_labels))):
      distances[gt_ind, pred_ind] += 1

  # Match objects
  row_ind, col_ind = linear_sum_assignment(distances)
  cost = distances[row_ind, col_ind]

  gt_track_ids = np.array([gt_box.track_id for gt_box in gt.regions])

  # Label as to if a given prediction is matched with a gt box of the same class
  gt_id_to_pred_box = {}

  for gt_idx, pred_idx, cost in zip(row_ind, col_ind, cost):
    if (1 - cost) > iou_threshold:
      gt_id_to_pred_box[gt_track_ids[gt_idx]] = pred.regions[pred_idx]

  return gt_id_to_pred_box


def extract_features(old_gt_frame, new_gt_frame, old_pred_frame, new_pred_frame,
                     old_gt_id_to_pred_box, new_gt_id_to_pred_box, frame_diff):
  """
    Function will extract features per predicted box and labels as to if
    each example is a True or False Positive
    Function operates on a single frame
    """
  # the features of all the pairs (which are comprised of either anchor/positive or anchor/negative) between the
  # new and old frames
  x = np.zeros((0, 4))
  # the labels of all the pairs (which are equal to 1 if the pair is anchor/positive, or 0 if the pair is anchor/negative)
  # between the new and old frames
  y = []

  # the ground truth track ids in the new frame
  new_gt_track_ids = np.array([new_box.track_id for new_box in new_gt_frame.regions])
  # the ground truth track ids in the old frames
  old_gt_track_ids = np.array([old_box.track_id for old_box in old_gt_frame.regions])

  # if there exists no ground truth tracks in either the old frame or the new frame, there are no ReID pairs possible
  if len(new_gt_track_ids) == 0 or len(old_gt_track_ids) == 0:
    return []

  # for each of the ground truth tracks in the old frame
  for old_gt_box_index in range(len(old_gt_frame.regions)):
    if old_gt_track_ids[old_gt_box_index] not in list(old_gt_id_to_pred_box.keys()):
      continue

    # find out which ground truth tracks in the new frame are matched to which predicted boxes in the new frame
    new_gt_track_ids_matched = np.array([
        new_gt_track_id in list(new_gt_id_to_pred_box.keys())
        for new_gt_track_id in new_gt_track_ids
    ])
    # the positive box is the box in the new frame which has the same track id as the old box. This is empty if the
    # ground truth track in the new frame is unmatched
    positive_index = np.where((new_gt_track_ids == old_gt_track_ids[old_gt_box_index]) &
                              new_gt_track_ids_matched)[0]
    if len(positive_index) == 0:
      # we have no data if the ground truth track in the new frame is unmatched, so continue
      continue
    else:
      positive_index = positive_index[0]

    # the candidates for the negative box are all of the boxes in the new frame which are matched to predictions,
    # but are of a different track id than the old box
    negative_track_candidates = np.where((new_gt_track_ids != old_gt_track_ids[old_gt_box_index]) &
                                         new_gt_track_ids_matched)[0]
    if len(negative_track_candidates) >= 1:
      negative_track_candidates = np.random.choice(negative_track_candidates, 1)

    # loop. The label is 0 if we are iterating on the positive box, 1 if we are iterating on the negative box
    for label, match_index in enumerate(
        np.concatenate([[positive_index], negative_track_candidates])):
      # the features of this pair
      features = []
      old_centroidwh, new_centroidwh = None, None
      old_embedding, new_embedding = None, None
      old_confidence, new_confidence = None, None
      # loop. If we are iterating over the new frame, the gt box index is either the positive or negative box
      # (depending on what which iteration in the outer match loop we are on) in the new frame,
      # the pred frame is the new frame, and is_new is True. If we are iterating over the old frame, the gt box index is the
      # anchor box in the olf frame, the pred frame is the old frame, and is_new is False.
      for gt_box_index, pred_frame, is_new in zip([match_index, old_gt_box_index],
                                                  [new_pred_frame, old_pred_frame], [True, False]):
        #  make sure that when we grab the box, it is in the appropriate frame (either new or old, depending on `is_new`)
        if not is_new:
          box = old_gt_id_to_pred_box[old_gt_track_ids[gt_box_index]]
        else:
          box = new_gt_id_to_pred_box[new_gt_track_ids[gt_box_index]]
        # get the features
        confidence = box.data.concepts[0].value
        bbox = box.region_info.bounding_box

        pixel_height = (bbox.bottom_row - bbox.top_row)
        pixel_width = (bbox.right_col - bbox.left_col)

        centroid_x = bbox.left_col + pixel_width / 2
        centroid_y = bbox.top_row + pixel_height / 2
        centroidwh = np.expand_dims([centroid_x, centroid_y, pixel_width, pixel_height], axis=0)

        # if there is no embedding for the box, we won't be able to calculate visual distances down the road
        if len(box.data.embeddings) == 0:
          continue
        # update old_{centroidwh, embedding} or new_{centroidwh, embedding} appropriately
        if not is_new:
          old_centroidwh = centroidwh
          old_embedding = np.expand_dims(box.data.embeddings[0].vector, axis=0)
          old_confidence = confidence
        else:
          new_centroidwh = centroidwh
          new_embedding = np.expand_dims(box.data.embeddings[0].vector, axis=0)
          new_confidence = confidence

      # make sure that the centroids and embeddings have been updated appropriately
      if isinstance(old_centroidwh, type(None)) or isinstance(new_centroidwh, type(None)):
        continue

      # append association errors
      for distance_key in ['iou', 'centroid_distance', 'confidence_distance', 'visual_distance']:
        distance_fn = distances[distance_key]
        association_errors = distance_fn(new_centroidwh, old_centroidwh, [[new_confidence]],
                                         [[old_confidence]], new_embedding, old_embedding, kf_states=[])[0]
        features.extend(association_errors)

      # append the features of the given anchor/positive or anchor/negative pair to the total list of features for this frame
      x = np.concatenate([x, [features]], axis=0)
      # append the label of the given anchor/positive or anchor/negative pair to the total list of features for this frame
      # (equal to 1 if the new box is positive, 0 if the new box is negative)
      y.append(label == 0)
  return x, y


def main():
  parser = argparse.ArgumentParser()
  # the predictions folder
  parser.add_argument("--databatch-folder", type=str)
  # the ground truth folder
  parser.add_argument("--gt-folder", type=str, default="")
  # the tag at the end of the model name
  parser.add_argument("--tag", type=str)
  # the minimum number of frames between the anchor box and the positive/negative boxes for ReID
  parser.add_argument("--min-frames", type=int)
  # the maximum number of frames between the anchor box and the positive/negative boxes for ReID
  parser.add_argument("--max-frames", type=int)
  # the number of frames to skip in a sequence
  parser.add_argument("--skip-frames", type=int)
  # path to save the output weights with the tag specified abovce
  parser.add_argument("--output", type=str)

  args = parser.parse_args()

  print("Loading DBs from %s" % args.databatch_folder)
  db_list, db_file_paths = load_databatches(args.databatch_folder)

  print("Performing Matching to GT using %s" % args.gt_folder)
  gt_list, _ = load_databatches(args.gt_folder)

  print(args.gt_folder)

  print("Generating Features")

  # the total list of features, across batches
  x = np.zeros((0, 4))
  # the total list of labels, across batches
  y = []
  total_length = 0
  for db, db_fp, gt_db in zip(db_list, db_file_paths, gt_list):
    total_length += 1

  cur_length = 0
  for db, db_fp, gt_db in zip(db_list, db_file_paths, gt_list):
    # the list of features, for this frame
    x_frame = np.zeros((0, 4))
    # the list of labels, for this frame
    y_frame = []

    ground_truth = gt_db.frames
    databatch = db.frames

    if len(ground_truth) != len(databatch):
      n = min(len(ground_truth), len(databatch))
      print("Warning: Mismatched lengths in ground truth ({}) and databatch ({}). Truncating to {}".format(len(ground_truth), len(databatch), n))
      ground_truth = ground_truth[:n]
      databatch = databatch[:n]

    # get ReID pairs for a random frame
    for frame_index in range(args.max_frames, len(ground_truth), args.skip_frames + 1):
      # get a random frame from the past to grab the anchor boxes (bounded in the past by args.min_frames and args.max_frames)
      random_frame_index = np.random.choice(
          range(frame_index - args.max_frames, frame_index - args.min_frames))
      # the ground truth in the frame in which the past anchor boxes reside
      old_gt_frame = ground_truth[random_frame_index].data
      # the predictions in the frame in which the past anchor boxes reside
      old_pred_frame = databatch[random_frame_index].data
      # match the predictions to the ground truth objects in the old frame, so we can grab the predictions, given the ground truth id
      old_gt_id_to_pred_box = match_regions(old_gt_frame, old_pred_frame)
      # the ground truth in the frame in which the positives/negatives reside
      new_gt_frame = ground_truth[frame_index].data
      # the predictions in the frame in which the positives/negatives reside
      new_pred_frame = databatch[frame_index].data
      # match the predictions to the ground truth objects in the new frame, so we can grab the predictions, given the ground truth id
      new_gt_id_to_pred_box = match_regions(new_gt_frame, new_pred_frame)

      # extract the features of all the pairs (which are comprised of either anchor/positive or anchor/negative) between the
      # new and old frames
      data = extract_features(
          old_gt_frame=old_gt_frame,
          new_gt_frame=new_gt_frame,
          old_pred_frame=old_pred_frame,
          new_pred_frame=new_pred_frame,
          old_gt_id_to_pred_box=old_gt_id_to_pred_box,
          new_gt_id_to_pred_box=new_gt_id_to_pred_box,
          frame_diff=frame_index - random_frame_index)
      # if there exists ground truth tracks in the old and new frames
      if len(data) == 2:
        # unpack the features and labels for this batch and append appropriately
        x_of_batch, y_of_batch = data
        x_frame = np.append(x_frame, x_of_batch, axis=0)
        y_frame.extend(y_of_batch)

    cur_length += 1
    print("Percentage Done: {}".format(cur_length / total_length))

    # append the features and labels for this frame to the total list of features and labels, across frames
    x = np.append(x, x_frame, axis=0)
    y.extend(y_frame)

  # split into train and test
  x_train, x_test, labels_train, labels_test = train_test_split(x, y, test_size=.1)

  linker = LogisticRegression()
  linker.fit(x_train, labels_train)

  confidence_test = linker.predict_proba(x_test)[:, 1]
  print("AP: {}".format(average_precision_score(labels_test, confidence_test)))

  os.makedirs(args.output, exist_ok=True)
  dump(
      linker,
      #open("/data/nfs/will.levine/trained_reid_function/models/{}".format(args.tag), "wb"),
      open((args.output + "/{}").format(args.tag), "wb"),
      protocol=2)


if __name__ == "__main__":
  main()
