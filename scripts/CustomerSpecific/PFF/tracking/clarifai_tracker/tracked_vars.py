from collections import deque
from itertools import islice
from typing import Deque, List

import numpy as np

# Maximum size of deques
MAX_LENGTH = 1000


class AbstractTrackedVar:

  def __init__(self):
    self.values = deque(maxlen=MAX_LENGTH)
    self.means = deque(maxlen=MAX_LENGTH)
    self.stddevs = deque(maxlen=MAX_LENGTH)
    self.trend = deque(maxlen=MAX_LENGTH)
    self.value = 0
    self.mean = 0
    self.stddev = 0

  def update(self, value):
    pass

  def __call__(self):
    return self.trend[-1]

  def __repr__(self):
    return "value: %f, mean: %f, stddev: %f" % (self.value, self.mean, self.stddev)

  def update_history(self, trend, stddev):
    self.trend.append(trend)

    #TODO: leaving self.means here for now; do we need it in the Abstract if we're tracking self.trend?
    self.mean = np.mean(np.abs(trend))
    self.stddev = np.mean(stddev)
    self.means.append(trend)
    self.stddevs.append(stddev)

  # overwrite deque with lst.
  def _update_deque(self, dq: Deque, lst: List):
    dq.clear()
    dq.append(lst)


class NonTrackedVar(AbstractTrackedVar):

  def __init__(self, normalize=False, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.normalize = normalize

  def update(self, value):
    self._update_deque(self.values, value)
    if self.normalize:
      self._update_deque(self.trend, value / np.linalg.norm(value))
    else:
      self._update_deque(self.trend, value)
    self.stddev = 0

  def update_history(self, *args, **kwargs):
    raise NotImplementedError()


class DebugTrackedVar(AbstractTrackedVar):

  def __init__(self, rand):
    self.rand = rand

  def update(self, value):
    self._update_deque(self.trend, value)

  def __call__(self):
    if self.rand:
      return np.random.random(self.trend[-1].shape)
    return np.zeros_like(self.trend[-1])

  def update_history(self, *args, **kwargs):
    raise NotImplementedError()


class MedianTrackedVar(AbstractTrackedVar):
  """
  Moving Median Tracked Var based on window
  """

  def __init__(self, window, normalize=False):
    super().__init__()
    self.normalize = normalize
    self.window = window

  def update(self, current_value):
    if self.normalize:
      current_value = current_value / np.linalg.norm(current_value)
    self.values.append(current_value)

    n_values = len(self.values)
    window = min(self.window, n_values)
    # self.values is a deque. Must use islice to get a slice.
    window_values = list(islice(self.values, n_values - window, n_values))
    med = np.median(window_values, axis=0)
    stddev = np.std(window_values, axis=0)

    self.update_history(med, stddev)


class EMATrackedVar(AbstractTrackedVar):
  """
  EMA Tracked var based on alpha
  """

  def __init__(self, alpha, normalize=False):
    super().__init__()
    self.alpha = alpha
    self.normalize = normalize

  def update(self, current_value):
    if self.normalize:
      current_value = current_value / np.linalg.norm(current_value)
    if np.any(np.isnan(current_value)):
      return
    if len(self.values) > 1:
      mean = self.ema_mean(current_value)
      stddev = np.sqrt((1 - self.alpha) * (self.stddevs[-1]**2 + self.alpha * np.sqrt(
          (current_value - self.means[-1])**2)))

    elif len(self.values):
      mean = self.ema_mean(current_value)
      stddev = np.std([mean, self.means[0]], axis=0)
    else:
      mean = current_value
      stddev = 0

    self.value = np.mean(current_value)
    self.values.append(current_value)
    self.update_history(mean, stddev)
    #logger.info("value: %f, mean: %f, stddev: %f", self.value, self.mean, self.stddev)

  def ema_mean(self, current_value):
    return self.alpha * current_value + (1 - self.alpha) * self.means[-1]


class MATrackedVar(AbstractTrackedVar):
  """
  Moving Average Tracked Var based on window
  """

  def __init__(self, window, normalize=False):
    super().__init__()
    self.normalize = normalize
    self.window = window

  def update(self, current_value):
    if self.normalize:
      current_value = current_value / np.linalg.norm(current_value)

    self.values.append(current_value)

    n_values = len(self.values)
    window = min(self.window, n_values)
    # self.values is a deque. Must use islice to get a slice.
    window_values = list(islice(self.values, n_values - window, n_values))
    mean = np.mean(window_values, axis=0)
    stddev = np.std(window_values, axis=0)

    self.value = np.mean(current_value)
    self.update_history(mean, stddev)
