import abc

import numpy as np
from scipy.spatial import distance, distance_matrix

from .box_utils import bbox_overlaps


def xywh2xyxy(boxes):
  boxes[:, 0] -= boxes[:, 2] / 2
  boxes[:, 1] -= boxes[:, 3] / 2
  boxes[:, 2] += boxes[:, 0]
  boxes[:, 3] += boxes[:, 1]
  return boxes


class Distance(abc.ABC):

  @abc.abstractmethod
  def __call__(self):
    pass


# Distance between centroids of tracks and dets
class CentroidDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    predicted_tracks = tracks[:, :2]
    detect_centroids = detections[:, :2]
    distances = distance.cdist(predicted_tracks, detect_centroids)
    return distances


# Normalized distance between box centroids (part of CIoU and DIoU)
class NormalizedCentroidDistance(CentroidDistance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    centroid_distance = super().__call__(tracks, detections, track_confidences,
                                         detection_confidences, track_embeddings,
                                         detection_embeddings, kf_states)
    centroid_distance_sq = centroid_distance**2  # squared centroid distance numerator

    tracks = xywh2xyxy(tracks.copy())
    detections = xywh2xyxy(detections.copy())

    # min and max dimensions to find smallest enclosing rect
    diags = np.zeros((tracks.shape[0], detections.shape[0]))
    for i in range(tracks.shape[0]):
      minx = np.minimum(tracks[i, 0], detections[:, 0])
      miny = np.minimum(tracks[i, 1], detections[:, 1])
      maxx = np.maximum(tracks[i, 2], detections[:, 2])
      maxy = np.maximum(tracks[i, 3], detections[:, 3])

      diags[i, :] = ((maxx - minx)**2 +
                     (maxy - miny)**2)  # no sqrt, see fig 6 https://arxiv.org/pdf/1911.08287.pdf

    return centroid_distance_sq / diags


# IoU between tracks and dets
class IoUDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    detections = xywh2xyxy(detections.copy())
    tracks = xywh2xyxy(tracks.copy())
    return 1 - bbox_overlaps(tracks, detections, include_edge_pixels=False)


# Euclidean distance of extracted features of tracks and detections
class EuclideanDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    vis_dist = distance_matrix(track_embeddings, detection_embeddings)
    return vis_dist


# Manhattan distance of extracted features of tracks and detections
class ManhattanDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    vis_dist = distance_matrix(track_confidences, detection_confidences, p=1)
    return vis_dist


# Euclidean distance of extracted features of tracks and detections
class NormalizedEuclideanDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    track_embeddings /= np.linalg.norm(track_embeddings, axis=1)[:, np.newaxis]
    detection_embeddings /= np.linalg.norm(detection_embeddings, axis=1)[:, np.newaxis]
    vis_dist = distance_matrix(track_embeddings, detection_embeddings)
    return vis_dist / 2

class MahalanobisDistance(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    mdist = np.zeros((len(kf_states), detections.shape[0]))
    norm_heuristic = 0.2

    for ii, kf in enumerate(kf_states):
      for jj in range(detections.shape[0]):
        eps = detections[jj,:].reshape(4,1) - np.dot(kf.A, kf.u)
        S = np.dot(kf.A, np.dot(kf.P, kf.A.T)) + kf.R
        SI = np.linalg.inv(S)
        mdist[ii,jj] = np.dot(eps.T,np.dot(SI,eps)) / norm_heuristic
        # actual UCMC paper had an extra term but from initial observations the log term dominates
        # without homography mapping so I'm leaving it out
        # NOTE: is the log determinant is likely huge because the coordinates are true pixel values
        # and not normalized from 0 to 1????
        # mdist[ii,jj] += np.log(np.linalg.det(S))
    
    return mdist

    # applied a crude normalization heuristic based on observed mdist values from log outputs
    # ~~~~~~~~~~~~
    # mdist stats:
    # ~~~~~~~~~~~~
    # mean          0.007394
    # std           0.011170
    # min = 3.433189086556674e-12
    # 25%           0.000008
    # 50%           0.002613
    # 75%           0.009654
    # max           0.150479

class MahalanobisDistance2(Distance):

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    mdist = np.zeros((len(kf_states), detections.shape[0]))
    norm_heuristic = 50

    for ii, kf in enumerate(kf_states):
      for jj in range(detections.shape[0]):
        eps = detections[jj,:].reshape(4,1) - np.dot(kf.A, kf.u)
        S = np.dot(kf.A, np.dot(kf.P, kf.A.T)) + kf.R
        SI = np.linalg.inv(S)
        mdist[ii,jj] = (np.dot(eps.T,np.dot(SI,eps)) + np.log(np.linalg.det(S)))  / norm_heuristic
        # actual UCMC paper had an extra term but from initial observations the log term dominates
        # without homography mapping so I'm leaving it out
        # NOTE: is the log determinant is likely huge because the coordinates are true pixel values
        # and not normalized from 0 to 1????
        # mdist[ii,jj] += np.log(np.linalg.det(S))
    
    return mdist

    # applied a crude normalization heuristic based on observed mdist values from log outputs
    # ~~~~~~~~~~~~
    # mdist stats:
    # ~~~~~~~~~~~~
    # mean          0.007394
    # std           0.011170
    # min = 3.433189086556674e-12
    # 25%           0.000008
    # 50%           0.002613
    # 75%           0.009654
    # max           0.150479


# Aggregates different distance functions, weighting them accordingly
class DistanceAggregator(Distance):

  def __init__(self, distances, weights=None):
    self.distances = distances
    self.weights = weights

  def __call__(self, tracks, detections, track_confidences, detection_confidences,
               track_embeddings, detection_embeddings, kf_states):
    dist_agg = 0
    if self.weights is None:
      self.weights = [1] * len(self.distances)

    for dist, weight in zip(self.distances, self.weights):
      dist_agg += dist(tracks, detections, track_confidences, detection_confidences,
                       track_embeddings, detection_embeddings, kf_states) * weight

    return dist_agg


# TODO: a distance registry will likely be necessary down the road, but want to see how these get used before making any decisions in that regard
distances = {
    "centroid_distance":
        CentroidDistance(),
    "iou":
        IoUDistance(),
    "viou":
        DistanceAggregator([IoUDistance(), NormalizedEuclideanDistance()], [0.5, 0.5]),
    "ciou":
        DistanceAggregator([IoUDistance(), ManhattanDistance()], [0.5, 0.5]),
    "diou":
        DistanceAggregator([IoUDistance(), NormalizedCentroidDistance()], [0.5, 0.5]),
    "vd":
        DistanceAggregator([NormalizedCentroidDistance(),
                            NormalizedEuclideanDistance()], [0.5, 0.5]),
    "visual_distance":
        NormalizedEuclideanDistance(),

    "confidence_distance":
        ManhattanDistance(),

    "mahalanobis_distance":
        MahalanobisDistance(),

    "mahalanobis_distance2":
        MahalanobisDistance2()
}
