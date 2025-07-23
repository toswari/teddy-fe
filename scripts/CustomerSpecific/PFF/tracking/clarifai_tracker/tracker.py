import operator
from typing import List, Optional

import numpy as np

from .abstract_motion_tracker import AbstractMotionTracker
from .hungarian_multitracker import Tracker


class KFTracker(AbstractMotionTracker):
  """ Kalman Filter trackers rely on the Kalman Filter algorithm to estimate the next position of an object
      based on its position and velocity in previous frames. Then detections are matched to predictions
      by using the Hungarian algorithm.
    """

  def __init__(self,
               track_aiid,
               min_confidence: float = 0.,
               association_confidence: List[float] = [0],
               max_disappeared: int = 15,
               min_visible_frames: int = 0,
               max_distance: float = 0.4,
               track_id_prefix: str = "",
               covariance_error: float = 1.0,
               observation_error: float = 0.1,
               distance_metric: str = "centroid_distance",
               initialization_confidence: float = 0.0,
               project_track: int = 0,
               use_detect_box: int = 1,
               project_without_detect: int = 1,
               project_fix_box_size: int = 0,
               detect_box_fall_back: float = 2.0,
               keep_track_in_image: int = 0,
               match_limit_ratio: float = -1,
               match_limit_min_matches: int = 3,
               optimal_assignment: int = 0,
               *args,
               **kwargs):
    """ __init__ docstring
        Args:
          min_confidence: This is the minimum confidence score for detections to be considered for tracking.
            {"min": 0, "max": 1}
          association_confidence: The list of association confidences to perform for each round.
          max_disappeared: This is the number of maximum consecutive frames a given object is allowed to
            be marked as "disappeared" until we need to deregister the object from tracking.
            {"min": 0, "max": 1000, "step": 1}
          min_visible_frames: only return tracks with minimum visible frames > min_visible_frames.
            {"min":0, "max":1000, "step": 1}
          max_distance: associate tracks with detections only when their distance is below max_distance (per round if a List)
          track_id_prefix: Prefix to add on to track to eliminate conflict
          covariance_error: Magnitude of the uncertainty on the initial state.
            {"min": 0, "max": "Infinity"}
          observation_error: Magnitude of the uncertainty on detection coordinates.
            {"min": 0, "max": "Infinity"}
          distance_metric: Distance metric for Hungarian matching
            [{"id":"centroid_distance"}, {"id":"iou"}, {"id":"visual_and_iou"}]
          initialization_confidence: Confidence for starting a new track. must be > min_confidence to have an effect.
            {"min": 0, "max": 1}
          project_track: How many frames in total to project box when detection isn't recorded for track.
            {"min":0, "max": 1000, "step": 1}
          use_detect_box: How many frames to project the last detection box, should be less than project_track_frames
            (1 is current frame).
            {"min":0, "max": 1000, "step": 1}
          project_without_detect: Whether to keep projecting the box forward if no detect is matched.
            {"min":0, "max": 1, "step": 1}
          project_fix_box_size: Whether to fix the box size when the track is in a project state
            {"min":0, "max": 1, "step": 1}
          detect_box_fall_back: Rely on detect box if association error is above this value
            {"min":0.0, "max": 2}
          keep_track_in_image: if this is 1, then push the tracker predict to stay inside image boundaries
            {"min": 0, "max": 1, "step": 1}
          match_limit_ratio: Multiplier to constrain association (< 1 is ignored) based on other associations
            {"min": -1.0, "max": 10.0}
          match_limit_min_matches: Min Number of matched tracks needed to invoke match limit
            {"min": 1, "max": 10, "step": 1}
          optimal_assignment: If True, rule out pairs with distance > max_distance before assignment
            {"min": 0, "max": 1, "step": 1}
        """
    super().__init__(*args, **kwargs)
    if not isinstance(max_distance, list) and not isinstance(max_distance, np.ndarray):
      max_distance = [max_distance]
    if len(association_confidence) != len(max_distance):
      raise Exception("Association Confidences must be same length as Max Distances")
    self.min_confidence = min_confidence
    self.association_confidence = association_confidence
    self.max_disappeared = max_disappeared
    self.min_visible_frames = min_visible_frames
    self.max_distance = max_distance
    self.detect_box_fall_back = detect_box_fall_back
    self.project_fix_box_size = project_fix_box_size
    self.project_without_detect = project_without_detect
    self.distance_metric = distance_metric
    self.initialization_confidence = initialization_confidence
    self.keep_track_in_image = keep_track_in_image
    self.match_limit_min_matches = match_limit_min_matches
    self.match_limit_ratio = match_limit_ratio
    self.kwargs = kwargs
    self.observation_error = observation_error
    self.covariance_error = covariance_error
    self.optimal_assignment = optimal_assignment

    if type(track_aiid) is str:
      if not len(track_aiid):
        self.track_aiid = []
      else:
        self.track_aiid = [track_aiid]
    else:
      self.track_aiid = track_aiid
    self.track_id_prefix = track_id_prefix

    self.config_kf = self.get_kf_config()

    # NOTE: With new params, add them to `init_state` method
    self.init_state()

    self.project_track = project_track
    self.use_detect_box = use_detect_box

    # Parameters for detector metadata (not all detectors may report metadata)
    self.detector_reporting_metadata = False
    self.detector_ran = True

    # tracks the dynamic state, -1 is default behavior
    self.dynamic_state = -1

  def get_kf_config(self):
    return {
        'dt': 1.0/30,  # assumes fixed frame rate for now
        'p_noise': self.covariance_error,
        'r_noise': self.observation_error
    }

  def get_multitracker_params(self):
    params = {
        "association_confidence": self.association_confidence,
        "dist_thresh": self.max_distance,
        "max_frames_to_skip": self.max_disappeared,
        "filter_config": self.config_kf,
        "dist_metric": self.distance_metric,
        "initialization_confidence": self.initialization_confidence,
        "project_without_detect": bool(self.project_without_detect),
        "project_fix_box_size": bool(self.project_fix_box_size),
        "detect_box_fall_back": self.detect_box_fall_back,
        "keep_track_in_image": bool(self.keep_track_in_image),
        "match_limit_ratio": self.match_limit_ratio,
        "match_limit_min_matches": self.match_limit_min_matches,
        "optimal_assignment": bool(self.optimal_assignment),
    }
    return params

  def reset_state(self):
    """Reset the state of the tracker"""
    params = self.get_multitracker_params()
    self.tracker = Tracker(**params, **self.kwargs)
    self.num_frames_processed = 0

  def unpack(self, frame_data):
    super().unpack(frame_data)
    self.centroids = []
    self.embeddings = []
    self.confidences = []
    for idx in self.valid_regions:
      region = frame_data.regions[idx]
      bbox = region.region_info.bounding_box
      width = bbox.right_col - bbox.left_col
      height = bbox.bottom_row - bbox.top_row
      self.centroids.append([[bbox.left_col + width / 2], [bbox.top_row + height / 2], [width],
                             [height]])
      if len(region.data.embeddings):
        self.embeddings.append(
            region.data.embeddings[0].vector)  #TODO handle multiple embeddings?
      else:
        self.embeddings.append([])
      self.confidences.append(region.value)

    self.check_metadata(frame_data)

  def pack(self, frame_data):
    """
    Reporting regions

    Relevant parameters:
      track.skipped_frames - number of frames since last detection (0 means matched to detection)
      self.project_track - how many frames after last detection to report tracks
        (0 means only report tracks matched to detections)
      self.use_detect_box - how many frames to use to report the detectors bounding box.
        (1 means report the detector box when matched to a track)

    Examples:
      project_track = 0, use_detect_box = 1 (default):
        Tracker only assigns track ids to detector outputs (previous behavior)
      project_track = 0, use_detect_box = 0:
        Tracker overwrites detection box, but does no projection
      project_track = 1, use_detect_box = 0:
        Tracker overwrites detection box and will report track box for one frame
        after last matched
      project_track = 1, use_detect_box = 2:
        Detector box will be reported when there is a match and 1 frame after:
      project_track = 1, use_detect_box > project_track:
        Same as above, projection governed by project_track
      project_track = 2, use_detect_box = 2:
        Detector box reported when matched and one frame after, then track box reported.

    See also py/svc/models/tests/test_kf_tracker.py
    """
    if self.valid_regions:  # skip if no detections
      for track_id, det_id in self.tracker.assignment.items():
        track = self.tracker.tracks[track_id]
        reg_id = self.valid_regions[det_id]
        region = frame_data.regions[reg_id]
        track.last_detection = region
        if self.show_track(track):
          region.track_id = self.track_id_prefix + str(track_id)
          self.pack_track_metadata(region, track)
          if self.use_detect_box == 0:
            overwrite_bbox(track.current_prediction, region.region_info.bounding_box)

    # Add projected boxes
    if self.project_track > 0 or not self.detector_ran:
      for track_id in self.tracker.unassigned_tracks:
        track = self.tracker.tracks[track_id]
        if self.show_track(track):
          region = frame_data.regions.add()
          region.CopyFrom(track.last_detection)
          region.track_id = self.track_id_prefix + str(track_id)
          if track.skipped_frames >= self.use_detect_box:
            overwrite_bbox(track.current_prediction, region.region_info.bounding_box)
          self.pack_track_metadata(region, track)
    self.pack_metadata(frame_data)
    self.num_frames_processed += 1

  def show_track(self, track):
    return track.skipped_frames <= self.project_track and len(
        track.trace) > self.min_visible_frames

  def update(self):
    #if self.valid_regions:  # skip if no detections
    self.tracker.Update(
        detections=self.centroids,
        embeddings=self.embeddings,
        confidences=self.confidences,
        detector_ran=self.detector_ran)
    self.association_error = self.tracker.association_error

  def set_state_from_proto(self):
    pass

  def get_state_proto(self):
    pass

  def __repr__(self) -> str:
    return "Kalman Filter Hungarian Tracker"

  def check_metadata(self, frame_data):
    """
    Method to check and track metadata.
    """
    #assert list(frame_data.metadata.keys()) != []
    if self.detector_reporting_metadata:
      self.detector_ran = "detector_metadata" in frame_data.metadata.keys()
    elif "detector_metadata" in frame_data.metadata.keys():
      self.detector_reporting_metadata = True

  def pack_track_metadata(self, region, track):
    track_dict = {
        "velocity": {
            "value": track.velocity.value,
            "mean": track.velocity.mean,
            "stddev": track.velocity.stddev
        },
        "acceleration": {
            "value": track.acceleration.value,
            "mean": track.acceleration.mean,
            "stddev": track.acceleration.stddev
        },
        "association_error": {
            "value": track.association_error.value,
            "mean": track.association_error.mean,
            "stddev": track.association_error.stddev
        }
    }
    region.data.metadata.update(track_dict)

  def pack_metadata(self, de):
    frame_dict = {
        "velocity": {
            "value": self.tracker.velocity.value,
            "mean": self.tracker.velocity.mean,
            "stddev": self.tracker.velocity.stddev
        },
        "acceleration": {
            "value": self.tracker.acceleration.value,
            "mean": self.tracker.acceleration.mean,
            "stddev": self.tracker.acceleration.stddev
        },
        "association_error": {
            "value": self.tracker.association_error.value,
            "mean": self.tracker.association_error.mean,
            "stddev": self.tracker.association_error.stddev
        },
        "matched_tracks": {
            "value": self.tracker.matched_tracks.value,
            "mean": self.tracker.matched_tracks.mean,
            "stddev": self.tracker.matched_tracks.stddev
        },
        "dynamic_state": self.dynamic_state
    }
    if self.track_id_prefix:
      meta_name = f"{self.track_id_prefix}_tracker_metadata"
    else:
      meta_name = "tracker_metadata"

    de.metadata.update({meta_name: frame_dict})


class DynamicKFTracker(KFTracker):
  """ Subclass of `KFTracker` that allows configurations switching
  see test_dynamic_kf_tracker.py and unittest_tracker_with_dynamic_tracking in trackers.yaml
  for usage
  """

  def __init__(self, dynamic_config=(), **kwargs):
    super().__init__(**kwargs)
    self.default_params = kwargs
    self.parse_dynamic_config(dynamic_config)
    self.dynamic_config = dynamic_config

  def parse_dynamic_config(self, dynamic_config):
    # all dynamic config properties must be set in default
    default_set = set(self.default_params.keys())

    for state in dynamic_config:
      assert set(state["params"].keys()).issubset(
          default_set), "Dynamic Config Keys must be defined in Default Set"
      state["parsed_conditions"] = {item[0]: item[1] for item in list(paths(state["conditions"]))}

  def unpack(self, frame_data):
    self.update_dynamic_state(frame_data)
    super().unpack(frame_data)

  def update_dynamic_state(self, frame_data):
    """ Checks metadata parameters and updates tracker configuration based on state
    """
    frame_dynamic_state = self.get_dynamic_state(frame_data)
    if frame_dynamic_state != self.dynamic_state:
      if frame_dynamic_state == -1:
        self.reset_config()
      else:
        params = self.get_config_params(frame_dynamic_state)
        self.set_config(**params)
        self.dynamic_state = frame_dynamic_state

  def get_dynamic_state(self, frame_data):
    """ Determines the dynamic state of the tracker based on metadata
    handles categorical as well as min/max value conditions
    """
    if not frame_data.metadata:
      return -1

    for state_num, state in enumerate(self.dynamic_config):
      conditions = state["parsed_conditions"]
      conditions_met = True
      for parameter, state_value in conditions.items():
        if parameter[-1] == "min":
          compare_func = operator.ge
          parameter = parameter[:-1]
        elif parameter[-1] == "max":
          compare_func = operator.lt
          parameter = parameter[:-1]
        else:
          compare_func = operator.eq

        metadata_value = frame_data.metadata
        metadata_present = True
        for key in parameter:
          if key not in metadata_value.keys():
            metadata_present = False
            conditions_met = False
            break
          metadata_value = metadata_value[key]
        if metadata_present:
          conditions_met = compare_func(metadata_value, state_value)
          if not conditions_met:
            break
        else:
          conditions_met = False
          break
      if conditions_met:
        return state_num

    return -1

  def get_config_params(self, dynamic_state):
    return self.dynamic_config[dynamic_state]["params"]

  def update_tracker_params(self):
    """ Any params, methods that are defined as functions of input params would be defined here
    """
    self.config_kf = self.get_kf_config()

  def set_config(self, **kwargs):
    """ Reset to default state, then update self and self.tracker params based on
    new state
    """
    self.reset_config()
    self.__dict__.update(**kwargs)
    self.update_tracker_params()
    params = self.get_multitracker_params()
    self.tracker.set_config(**params)

  def reset_config(self):
    """ Reset to default state
    """
    self.dynamic_state = -1
    self.__dict__.update(self.default_params)
    self.update_tracker_params()
    self.tracker.reset_config()


def paths(tree, cur=()):
  """ Function to get paths from dict
  """
  if not tree or type(tree) != dict:
    yield (cur, tree)
  else:
    for n, s in tree.items():
      for path in paths(s, cur + (n,)):
        yield path


def overwrite_bbox(centroidwh, bbox):
  x, y, width, height = centroidwh
  width = np.abs(width)[0]
  height = np.abs(height)[0]
  width = np.maximum(width, 0)
  height = np.maximum(height, 0)
  bbox.left_col = float(x[0] - width / 2)
  bbox.top_row = float(y[0] - height / 2)
  bbox.right_col = float(x[0] + width / 2)
  bbox.bottom_row = float(y[0] + height / 2)
