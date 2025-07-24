import numpy as np
from joblib import load
from scipy.optimize import linear_sum_assignment

from .visual_reid import VisualReID
from .tracked_vars import (DebugTrackedVar, EMATrackedVar,
                                                         MATrackedVar, MedianTrackedVar,
                                                         NonTrackedVar)
from .distance_utils import distances
from .hungarian_multitracker import Track
from .tracker import KFTracker

# import logging

VAR_TRACKER_MAP = {
    "med": (MedianTrackedVar, [150]),
    "ema": (EMATrackedVar, [0.50, False]),
    "ma": (MATrackedVar, [150, False]),
    "na": (NonTrackedVar, [False]),
    "mednorm": (MedianTrackedVar, [150, True]),
    "emanorm": (EMATrackedVar, [0.50, True]),
    "manorm": (MATrackedVar, [150, True]),
    "nanorm": (NonTrackedVar, [True]),
    "rand": (DebugTrackedVar, [True]),
    "zero": (DebugTrackedVar, [False]),
}


class TrackConstructor:

  def __init__(self, var_tracker):
    self.var_tracker_params = VAR_TRACKER_MAP[var_tracker]

  def __call__(self, *args, **kwargs):
    track = Track(*args, **kwargs)
    track.embedding = self.var_tracker_params[0](*self.var_tracker_params[1])
    track.embedding.update(np.array(kwargs["embeddings"]))
    return track


class KalmanREID(KFTracker):

  def __init__(self,
               max_emb_distance: float = float('inf'),
               max_dead: float = float('inf'),
               var_tracker: str = "na",
               reid_model_path: str = "",
               *args,
               **kwargs):
    """ __init__ docstring
          Args:
            max_emb_distance: Max embedding distance to be considered a re-identification
              {"min": 0, "max": "Infinity"}
            max_dead: Max number of frames for track to be dead before we re-assign the ID
              {"min": 1, "max": "Infinity"}
            var_tracker: String that determines how embeddings from multiple timesteps are aggregated, defaults to "na" (most recent embedding overwrites past embeddings)
              [{"id":"med"}, {"id":"ma"}, {"id":"ema"}, {"id":"na"}]
            reid_model_path: The path to the linker
      """
    self.max_emb_distance = max_emb_distance
    self.var_tracker = var_tracker
    self.reid_model_path = reid_model_path
    self.reid_model = VisualReID() if self.reid_model_path == "" else load(self.reid_model_path)
    self.distance_dict = distances
    self.max_dead = max_dead

    super().__init__(*args, **kwargs)
    self.tracker.track_constructor = TrackConstructor(self.var_tracker)
    self.vd = distances['vd']

  def __repr__(self):
    return "Kalman Re-ID Tracker"

  def reset_state(self):
    super().reset_state()
    self.tracker.track_constructor = TrackConstructor(self.var_tracker)

  def update(self):
    super().update()
    # alive tracks
    tracks = self.tracker.tracks
    # dead tracks
    dead_tracks = self.tracker.dead_tracks

    # listify so we have a fixed list of strs detached from state of dict
    curr_trackids = list(tracks.keys())
    curr_dead_trackids = list(self.tracker.dead_tracks.keys())

    # list of tracks that are new
    new_track_ids = []
    for trackid in curr_trackids:
      if tracks[trackid].track_len == 0:  # new track
        new_track_ids.append(trackid)
    new_track_ids = np.array(new_track_ids)

    if len(new_track_ids) == 0:
      return

    new_track_embeddings = np.array([tracks[ii].embedding() for ii in new_track_ids])
    new_track_indices_with_embeddings = np.array(
        [i for i in range(len(new_track_embeddings)) if len(new_track_embeddings[i]) > 0])

    if len(new_track_indices_with_embeddings) == 0:
      return

    new_track_embeddings = new_track_embeddings[new_track_indices_with_embeddings]
    new_track_ids = new_track_ids[new_track_indices_with_embeddings]

    new_track_locations = np.array([tracks[ii].prediction[:4] for ii in new_track_ids]).squeeze(2)

    new_track_confidences = np.array([tracks[ii].confidence for ii in new_track_ids])

    # list of tracks that weren't alive for very long
    young_dead_track_ids = []
    for d_trackid in curr_dead_trackids:
      if self.tracker.dead_tracks[d_trackid].track_len < self.max_dead:
        young_dead_track_ids.append(d_trackid)
    young_dead_track_ids = np.array(young_dead_track_ids)

    if len(young_dead_track_ids) == 0:
      return

    dead_track_embeddings = np.array([dead_tracks[ii].embedding() for ii in young_dead_track_ids])
    dead_track_indices_with_embeddings = np.array(
        [i for i in range(len(dead_track_embeddings)) if len(dead_track_embeddings[i]) > 0])

    if len(dead_track_indices_with_embeddings) == 0:
      return

    dead_track_embeddings = dead_track_embeddings[dead_track_indices_with_embeddings]
    young_dead_track_ids = young_dead_track_ids[dead_track_indices_with_embeddings]

    dead_track_locations = np.array(
        [dead_tracks[ii].prediction[:4] for ii in young_dead_track_ids]).squeeze(2)
    dead_track_embeddings = np.array([dead_tracks[ii].embedding() for ii in young_dead_track_ids])
    dead_track_confidences = np.array([dead_tracks[ii].confidence for ii in young_dead_track_ids])

    features = np.zeros((len(new_track_embeddings), len(dead_track_embeddings), 4))

    for distance_index, distance_str in enumerate(
        ['iou', 'centroid_distance', 'confidence_distance', 'visual_distance']):
      distance_fn = self.distance_dict[distance_str]
      association_error = distance_fn(new_track_locations, dead_track_locations,
                                      np.expand_dims(new_track_confidences, axis=-1),
                                      np.expand_dims(dead_track_confidences, axis=-1),
                                      new_track_embeddings, dead_track_embeddings, None)
      # NOTE: setting kf_states to None for now - not used in the distance functions (clean up later)
      features[:, :, distance_index] = association_error

    distances = np.zeros((len(new_track_embeddings), len(dead_track_embeddings)))
    for new_track_idx in range(len(features)):
      distances[new_track_idx] = self.reid_model.predict_proba(features[new_track_idx])[:, 0]

    # linear sum assignment
    assigned_rows, assigned_columns = linear_sum_assignment(distances)
    assigned_distances = distances[assigned_rows, assigned_columns]
    for assigned_row, assigned_column, assigned_distance in zip(assigned_rows, assigned_columns,
                                                                assigned_distances):
      if assigned_distance <= self.max_emb_distance:  # make sure we're only performing reid for low embedding distances
        self.tracker.ReviveTrackId(new_track_ids[assigned_row],
                                   young_dead_track_ids[assigned_column])


