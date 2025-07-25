import abc

import numpy as np


class VisualReID(abc.ABC):

  def predict_proba(self, x):
    return np.array([[x[i, -1], 1 - x[i, -1]] for i in range(len(x))])
