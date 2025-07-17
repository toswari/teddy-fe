"""
This file implements the assigning process between detections and tracks for the multi object tracking.
It updates track vectors using following steps:
    - Create tracks if no tracks vector found
    - Calculate cost using sum of square distance
      between predicted vs detected centroids
    - Using Hungarian Algorithm assign the correct
      detected measurements to predicted tracks
      https://en.wikipedia.org/wiki/Hungarian_algorithm
    - Identify tracks with no assignment, if any
    - If tracks are not detected for long time, remove them
    - Now look for un_assigned detects
    - Start new tracks
    - Update KalmanFilter state, lastResults and tracks trace
"""
import numpy as np
from scipy.optimize import linear_sum_assignment

from .tracked_vars import EMATrackedVar, NonTrackedVar
from .distance_utils import distances
from .kalman_filter_noise_comp import KalmanFilter

class Track:
  """Track class for every object to be tracked
    Attributes:
        None
    """

  def __init__(self,
               prediction,
               confidence,
               trackIdCount,
               filter_config,
               embeddings=None,
               velocity_alpha=0.1,
               acceleration_alpha=0.1,
               association_alpha=0.1):
    """Initialize variables used by Track class
        Args:
            prediction: predicted centroids of object to be tracked
            trackIdCount: identification of each track object
            filter_config: config to set up kalman filter
            embeddings: embeddings for detections
        Return:
            None
        """
    self.track_id = trackIdCount  # identification of each track object
    self.KF = KalmanFilter(**filter_config)  # KF instance to track this object
    self.current_prediction = np.asarray(prediction)  # current frame predicted coordinates (x,y)
    self.prediction = self.current_prediction  # next frame
    self.skipped_frames = 0  # number of frames skipped undetected
    self.trace = [np.asarray(prediction)]  # trace path
    self.KF.u[0:4] = np.asarray(prediction)
    self.embedding = NonTrackedVar()
    self.embedding.update(np.asarray(embeddings))

    self.velocity = EMATrackedVar(alpha=velocity_alpha)
    self.acceleration = EMATrackedVar(alpha=acceleration_alpha)

    self.association_error = EMATrackedVar(alpha=association_alpha)

    self.track_len = 0

    self.confidence = confidence

  def __repr__(self):
    return f"Track(track_id={self.track_id}, current_prediction={self.current_prediction}, skipped_frames={self.skipped_frames})"


class Tracker:
  """Tracker class that updates track vectors of object tracked"""

  def __init__(self,
               association_confidence,
               dist_thresh,
               max_frames_to_skip,
               filter_config,
               trackIdCount=0,
               dist_metric="centroid_distance",
               initialization_confidence=0.0,
               project_without_detect=True,
               project_fix_box_size=False,
               detect_box_fall_back=2,
               keep_track_in_image=False,
               match_limit_ratio=-1,
               match_limit_min_matches=3,
               optimal_assignment=False,
               **dist_kwargs):
    """Initialize variable used by Tracker class
        Args:
            association_confidence: the list of association confidences
                                     for each round
            dist_thresh: distance thresholds per round. When exceeds the threshold,
                         track will be deleted and new track is created
            filter_config: hyperparameters for smoothing function
            max_frames_to_skip: maximum allowed frames to be skipped for
                                the track object undetected
            trackIdCount: identification of each track object
            dist_metric: metric used to calculate pairwise distance between tracks and detections
            initialization_confidence: track initialization confidence.
            project_without_detect: update KF projection if no detection is matched
            project_fix_box_size: lock box size during projection
            detect_box_fall_back: fall back on detection box if association error is above this value
            match_limit_ratio: multiplier for mean association error to keep a match
            optimal_assignment: If True, rule out pairs with distance > dist_thresh before assignment
        Return:
            None
        """

    # Changeable Parameters
    self.set_config(
        set_default=True,
        association_confidence=association_confidence,
        dist_thresh=dist_thresh,
        max_frames_to_skip=max_frames_to_skip,
        project_without_detect=project_without_detect,
        project_fix_box_size=project_fix_box_size,
        initialization_confidence=initialization_confidence,
        detect_box_fall_back=detect_box_fall_back,
        keep_track_in_image=keep_track_in_image,
        match_limit_ratio=match_limit_ratio,
        match_limit_min_matches=match_limit_min_matches,
        dist_metric=dist_metric,
        filter_config=filter_config,
        optimal_assignment=optimal_assignment,
        dist_kwargs=dist_kwargs)

    # State
    self.tracks = {}
    self.dead_tracks = {}
    self.assignment = {}
    self.association_error = EMATrackedVar(0.1)
    self.velocity = EMATrackedVar(0.1)
    self.acceleration = EMATrackedVar(0.1)
    self.matched_tracks = EMATrackedVar(0.1)

    self.track_constructor = Track

    self.trackIdCount = trackIdCount

  def set_config(self, set_default=False, **kwargs):
    """
    Set default config or update config
    """
    if set_default:
      self.__default_params__ = kwargs
    else:
      assert all([k in self.__default_params__.keys()
                  for k in kwargs]), "Tried to set non-existent parameter"
    self.__dict__.update(**kwargs)
    self.distance_fn = distances[self.dist_metric]
    self.diou = distances['diou']

  def reset_config(self):
    """
    Reset Config to Defaults
    """
    self.__dict__.update(self.__default_params__)
    self.distance_fn = distances[self.dist_metric]

  def ReviveTrackId(self, alive_trackid, dead_trackid):
    assert dead_trackid not in self.tracks, "Cannot 'revive' trackid that's currently in use;\n\tTried to re-assign track ID %s to %s, which was already in use" % (
        alive_trackid, dead_trackid)
    self.tracks[dead_trackid] = self.tracks[alive_trackid]
    del self.tracks[alive_trackid]
    del self.dead_tracks[dead_trackid]

    if alive_trackid in self.assignment:
      self.assignment[dead_trackid] = self.assignment[alive_trackid]
      del self.assignment[alive_trackid]
    elif alive_trackid in self.unassigned_tracks:
      self.unassigned_tracks[self.unassigned_tracks.index(alive_trackid)] = dead_trackid

  def Update(self, detections, embeddings, confidences=None, detector_ran=True):
    """
        Update tracks vector using following steps:
            - Create tracks if no tracks vector found
            - Calculate cost using sum of square distance
              between predicted vs detected centroids
            - Using Hungarian Algorithm assign the correct
              detected measurements to predicted tracks
              https://en.wikipedia.org/wiki/Hungarian_algorithm
            - Identify tracks with no assignment, if any
            - If tracks are not detected for long time, remove them
            - Now look for un_assigned detects
            - Start new tracks
            - Update KalmanFilter state, lastResults and tracks trace
        Args:
            detections: detected centroids of object to be tracked
            embeddings: embedding vectors for each detection
            confidences: (optional) detection confidence values, ignored if empty
        Return:
            None
        """
    expired_dead_tracks = []
    for d_trackid in self.dead_tracks:
      self.dead_tracks[d_trackid].track_len += 1  # used to track length a track has been dead
      if self.dead_tracks[d_trackid].track_len > 500:
        expired_dead_tracks.append(d_trackid)

    for tid in expired_dead_tracks:
      del self.dead_tracks[tid]

    for track_id in self.tracks:
      self.tracks[track_id].track_len += 1

    # Create tracks if no tracks vector found and skip matching
    if (len(self.tracks) == 0):
      for i in range(len(detections)):
        if confidences is None or confidences[i] >= self.initialization_confidence:
          track = self.track_constructor(
              detections[i],
              confidences[i],
              self.trackIdCount,
              self.filter_config,
              embeddings=embeddings[i])
          self.tracks[self.trackIdCount] = track
          self.assignment[self.trackIdCount] = i
          self.trackIdCount += 1
      self.unassigned_tracks = []
      return

    track_ids = np.array(list(self.tracks.keys()))
    predicted_tracks = np.array([self.tracks[ii].prediction[:4] for ii in track_ids]).squeeze(2)
    kf_states = np.array([self.tracks[ii].KF for ii in track_ids])
    track_embeddings = np.array([self.tracks[ii].embedding() for ii in track_ids])
    track_confidences = np.array([self.tracks[ii].confidence for ii in track_ids])

    if detections:
      detections = np.array(detections)
    else:
      detections = np.zeros([0, 4, 1])

    detection_embeddings = np.array(embeddings)
    if confidences is not None:
      confidences = np.array(confidences)

    assigned_track_booleans = np.zeros(track_ids.shape[0], dtype=bool)
    assigned_detect_booleans = np.zeros(detections.shape[0], dtype=bool)

    unassigned_track_booleans = np.ones(track_ids.shape[0], dtype=bool)
    unassigned_detect_booleans = np.ones(detections.shape[0], dtype=bool)

    assigned_track_ids = []
    assigned_detect_ids = []
    assigned_cost = []

    for dist_thresh, association_confidence in zip(self.dist_thresh, self.association_confidence):
      unassigned_detect_booleans_greater_than_confidence = unassigned_detect_booleans.copy()
      unassigned_detect_booleans_greater_than_confidence[np.where(
          confidences <= association_confidence)[0]] = False

      if len(track_embeddings[unassigned_track_booleans]) > 0 and len(
          detection_embeddings[unassigned_detect_booleans_greater_than_confidence]) > 0:
        if np.all([len(track_embeddings[i]) > 0 for i in unassigned_track_booleans]) and np.all([
            len(detection_embeddings[i]) > 0
            for i in unassigned_detect_booleans_greater_than_confidence
        ]):
          distances = self.distance_fn(
              predicted_tracks[unassigned_track_booleans],
              detections.squeeze(2)[unassigned_detect_booleans_greater_than_confidence],
              np.expand_dims(track_confidences, axis=-1)[unassigned_track_booleans],
              np.expand_dims(confidences,
                             axis=-1)[unassigned_detect_booleans_greater_than_confidence],
              track_embeddings[unassigned_track_booleans],
              detection_embeddings[unassigned_detect_booleans_greater_than_confidence], kf_states)
        else:
          distances = self.diou(
              predicted_tracks[unassigned_track_booleans],
              detections.squeeze(2)[unassigned_detect_booleans_greater_than_confidence],
              np.expand_dims(track_confidences, axis=-1)[unassigned_track_booleans],
              np.expand_dims(confidences,
                             axis=-1)[unassigned_detect_booleans_greater_than_confidence],
              track_embeddings[unassigned_track_booleans],
              detection_embeddings[unassigned_detect_booleans_greater_than_confidence], kf_states)

      else:
        distances = np.zeros((len(track_embeddings[unassigned_track_booleans]), len(
            detection_embeddings[unassigned_detect_booleans_greater_than_confidence])))

      # Using Hungarian Algorithm assign the correct detected measurements
      # to predicted tracks
      if self.optimal_assignment:
        distances[distances > dist_thresh] = 2
      row_ind, col_ind = linear_sum_assignment(distances)

      cost = distances[row_ind, col_ind]
      # PUB-476: Prevent numpy warning when np.mean operates on empty list.
      if len(cost):
        self.association_error.update(np.mean(cost))

      # Reduce overall dist_thresh based on association error if enabled
      if self.match_limit_ratio >= 1 and len(self.tracks) > self.match_limit_min_matches:
        stddev_error = max(self.association_error.stddev, 0.05)
        dist_thresh = min(self.match_limit_ratio * stddev_error + self.association_error.value,
                          dist_thresh)

      # includes cost filtering
      assigned_track_ids.extend(
          track_ids[np.where(unassigned_track_booleans == True)[0]][row_ind][cost <= dist_thresh])
      assigned_detect_ids.extend(
          np.where(unassigned_detect_booleans_greater_than_confidence == True)[0][col_ind][
              cost <= dist_thresh])
      assigned_cost.extend(cost[cost <= dist_thresh])

      assigned_track_booleans[np.where(
          unassigned_track_booleans == True)[0][row_ind[cost <= dist_thresh]]] = True
      assigned_detect_booleans[np.where(unassigned_detect_booleans_greater_than_confidence == True)
                               [0][col_ind[cost <= dist_thresh]]] = True

      unassigned_track_booleans = ~assigned_track_booleans
      unassigned_detect_booleans = ~assigned_detect_booleans

    unassigned_track_ids = track_ids[~assigned_track_booleans]

    # Confirm lengths match
    # assert len(unassigned_track_inds) + len(assigned_track_ids) == len(track_ids)
    self.assignment = dict(zip(assigned_track_ids, assigned_detect_ids))

    # Identify tracks with no assignment, if any
    self.unassigned_tracks = []
    for track_id in unassigned_track_ids:
      if detector_ran:
        self.tracks[track_id].skipped_frames += 1
      # If tracks are not detected for long time, remove them
      if (self.tracks[track_id].skipped_frames > self.max_frames_to_skip):
        self.dead_tracks[track_id] = self.tracks[track_id]
        self.dead_tracks[track_id].track_len = 0
        del self.tracks[track_id]
      else:
        self.unassigned_tracks.append(track_id)

    # Now look for un_assigned detects
    assigned_confidences = np.array(confidences)[assigned_detect_booleans]

    if not self.initialization_confidence:
      unassigned_detect_inds = np.where(~assigned_detect_booleans)[0]
    elif confidences is not None:
      unassigned_detect_inds = np.where(~assigned_detect_booleans &
                                        (confidences > self.initialization_confidence))[0]
    else:
      raise ValueError("Initialization confidence specified but no confidence values passed")

    # Start new tracks
    for det_ind in unassigned_detect_inds:
      track = self.track_constructor(
          detections[det_ind],
          confidences[det_ind],
          self.trackIdCount,
          self.filter_config,
          embeddings=detection_embeddings[det_ind])
      self.tracks[self.trackIdCount] = track
      self.assignment[self.trackIdCount] = det_ind
      self.trackIdCount += 1

    # Update KalmanFilter state, lastResults and tracks trace
    self.update_matched(assigned_track_ids, detections, detection_embeddings, assigned_cost,
                        assigned_confidences)

    # Project unmatched tracks
    if self.project_without_detect:
      self.update_unmatched(self.unassigned_tracks)

    # keep tracker inside the image boundary,
    # for both current/corrected and future predictions
    if self.keep_track_in_image:
      for track_id in self.tracks:
        self.tracks[track_id].prediction = self.adjust_box_within_image(
            self.tracks[track_id].prediction)
        self.tracks[track_id].current_prediction = self.adjust_box_within_image(
            self.tracks[track_id].current_prediction)

  def update_matched(self, ids, detections, detection_embeddings, assigned_cost,
                     assigned_confidences):
    """
    Correct KF projections and update project for next frame when detection was matched
    """

    self.update_track_association_error(ids, assigned_cost)

    velocities = []
    accelerations = []
    for track_id, cost, confidence in zip(ids, assigned_cost, assigned_confidences):
      self.tracks[track_id].prediction = self.tracks[track_id].KF.correct(
          detections[self.assignment[track_id]], 1)

      self.tracks[track_id].confidence = confidence

      # Set internal and external xywh to detection if cost was too high
      if cost > self.detect_box_fall_back:
        self.tracks[track_id].prediction[:4] = detections[self.assignment[track_id]]
        self.tracks[track_id].KF.u[:4] = detections[self.assignment[track_id]]
      if len(detection_embeddings[self.assignment[track_id]]):
        if len(np.asarray(detection_embeddings[self.assignment[track_id]])) > 0 and len(
            self.tracks[track_id].embedding.trend[-1]) > 0:
          self.tracks[track_id].embedding.update(
              np.asarray(detection_embeddings[self.assignment[track_id]]))

      self.tracks[track_id].current_prediction = self.tracks[track_id].prediction.copy()
      self.tracks[track_id].prediction = self.tracks[track_id].KF.predict()[0:4]

      self.tracks[track_id].skipped_frames = 0

      self.tracks[track_id].trace.append(detections[self.assignment[track_id]])

      # Calculate track velocity
      velocity = self.tracks[track_id].trace[-1] - self.tracks[track_id].trace[-2]
      self.tracks[track_id].velocity.update(velocity)
      velocities.append(velocity[0:2])

      # Calculate track acceleration
      if len(self.tracks[track_id].velocity.values) > 2:
        acceleration = self.tracks[track_id].velocity.values[-1] - self.tracks[track_id].velocity.values[-2]
        self.tracks[track_id].acceleration.update(acceleration)
        accelerations.append(acceleration[0:2])

    # PUB-476: Prevent numpy warning when np.mean operates on empty list.
    if len(velocities):
      velocity_mean = np.mean(np.array(velocities), axis=0)
      self.velocity.update(velocity_mean)
    
    if len(accelerations):
      acceleration_mean = np.mean(np.array(accelerations), axis=0)
      self.acceleration.update(acceleration_mean)

    self.matched_tracks.update(len(ids))

  def update_unmatched(self, ids):
    """
    Update kf projections when no detection was matched (skipping correct)
    """
    for track_id in ids:
      self.tracks[track_id].current_prediction = self.tracks[track_id].prediction.copy()
      u = self.tracks[track_id].KF.predict()
      if not self.project_fix_box_size:
        self.tracks[track_id].prediction = u[0:4]
      else:
        # Only update the location
        self.tracks[track_id].prediction[:2] = u[:2]
        self.tracks[track_id].KF.u[2:4] = self.tracks[track_id].prediction[2:4]

  def update_track_association_error(self, ids, cost):
    for track_id, association_error, in zip(ids, cost):
      #  if association_error < dist_thresh:
      self.tracks[track_id].association_error.update(association_error)

  def adjust_box_within_image(self, box):
    # box: np.array(4,1), cx, cy, w, h
    box[:2][box[:2] < 0] = 0
    box[:2][box[:2] > 1] = 1
    return box
