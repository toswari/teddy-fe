import abc

from google.protobuf.any_pb2 import Any
from typing import final

class AbstractTracker(abc.ABC):
  """
  Online tracker.
  """

  def __init__(self, existing_tracks=tuple()):
    self.all_tracks = []
    self.track_indices = {track.id: idx for idx, track in enumerate(existing_tracks)}

  @abc.abstractmethod
  def unpack(self, frame_data):
    """
    Parse input frame, returns the args necessary to call update()
    """

  @abc.abstractmethod
  def update(self):
    """
    Implement tracker logic here
    """

  @abc.abstractmethod
  def pack(self, frame_data):
    """
    Get original frame_data and update it in place with the result of update.
    """

  @final
  def set_state_from_proto(self, state_any):
    state_any.Unpack(self.state)

  def export_state_proto(self):
    """
    Convert custom state type to state proto.
    """

  def reset_state(self):
    """
    Reset the tracker state to initial conditions.
    """

  @final
  def init_state(self):
    self.track_indices = {}
    self.all_tracks = []
    self.reset_state()

  def export_tracks(self):
    """
    Ensure tracks are exported to Track proto.
    """

  @final
  def write_tracks(self, video_example):
    self.export_tracks()
    # Make sure tracks come back in order order by id.
    # Note: checks if track ids are string versions of integers so sort by their int values in that
    # case but fall back to t.id otherwise.
    all_tracks = sorted(self.all_tracks, key=lambda t: int(t.id) if t.id.isdigit() else t.id)
    for track in all_tracks:
      track_idx = self.track_indices.get(track.id)
      if track_idx:
        video_example.track[track_idx].CopyFrom(track)
      else:
        video_example.track.extend([track])

  @final
  def get_state_proto(self):
    self.export_state_proto()
    state_any = Any()
    state_any.Pack(self.state)
    return state_any

  @final
  def __call__(self, frame_data):
    self.unpack(frame_data)
    self.update()
    self.pack(frame_data)

  @abc.abstractmethod
  def __repr__(self) -> str:
    ...
