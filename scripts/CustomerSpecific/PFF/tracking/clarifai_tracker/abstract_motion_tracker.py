import abc

from .abstract_tracker import AbstractTracker

class AbstractMotionTracker(AbstractTracker):

  @abc.abstractmethod
  def __init__(self,
               track_aiid=None,
               min_confidence: float = 0.,
               max_disappeared: int = 15,
               min_visible_frames: int = 0,
               max_distance: float = 0.4,
               track_id_prefix: str = "",
               *args,
               **kwargs):
    """ __init__ docstring
        Args:
          min_confidence: This is the minimum confidence score for detections to be considered for tracking.
            {"min": 0, "max": 1}
          max_disappeared: This is the number of maximum consecutive frames a given object is allowed to
            be marked as "disappeared" until we need to deregister the object from tracking.
            {"min": 0, "max": 1000, "step": 1}
          min_visible_frames: only return tracks with minimum visible frames > min_visible_frames.
            {"min":0, "max":1000, "step": 1}
          max_distance: associate tracks with detections only when their distance is below max_distance.
            {"min":0, "max":1.41}
          track_id_prefix: Prefix to add on to track to eliminate conflicts
    """
    super().__init__(*args, **kwargs)
    self.min_confidence = min_confidence
    self.max_disappeared = max_disappeared
    self.min_visible_frames = min_visible_frames
    self.max_distance = max_distance

    if isinstance(track_aiid, str):
      if not track_aiid:
        self.track_aiid = []
      else:
        self.track_aiid = [track_aiid]
    else:
      self.track_aiid = track_aiid
    self.track_id_prefix = track_id_prefix
    self.association_error = None  # init value to avoid AttributeError when running context trackers

  @abc.abstractmethod
  def unpack(self, frame_data):
    self.valid_regions = []
    for ii, reg in enumerate(frame_data.regions):
      if self.track_aiid:
        tracked_aiid = False
        for concept in reg.data.concepts:
          if concept.name in self.track_aiid:
            tracked_aiid = True
            continue
      else:
        tracked_aiid = True

      if reg.value > self.min_confidence:
        confident_detection = True
      else:
        confident_detection = False
      if tracked_aiid and confident_detection:
        self.valid_regions.append(ii)
