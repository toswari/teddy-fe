import numpy as np


class KalmanFilter:
  """Kalman Filter class keeps track of the estimated state of
    the system and the variance or uncertainty of the estimate.
    Predict and Correct methods implement the functionality
    Reference: https://en.wikipedia.org/wiki/Kalman_filter
    Attributes: None
    """

  def __init__(self, dt, r_noise, p_noise):
    """Initialize variable used by Kalman Filter class
        Args:
            delta_time: dt time for velocities
            p_noise: covariance error. Could be something big as there is uncertainty in the beginning
            r_noise: observation error. In our case this is the error in detection coordinates
        Return:
            None
        """

    self.A = np.array([[1, 0, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0, 0],
                       [0, 0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0, 0]])  # matrix in observation equations
    self.u = np.zeros((8, 1))  # previous state vector

    # (cx, cy, w, h, cxv, cyv, wv, hv) tracking object coords and velocities
    self.b = np.array([[0], [0], [0], [0], [0], [0], [0], [0]])  # vector of observations

    self.P = np.diag((1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)) * p_noise  # covariance matrix

    # we are predicting 4 coordinates
    # constructing state transition mat
    self.F = np.eye(2 * 4, 2 * 4)
    for i in range(4):
      self.F[i, 4 + i] = dt

    Q0 = np.eye(4) * 10  # process noise matrix (in UCMC paper they initialize this to 5 along diagonal) (make this an input param?)
    G = np.zeros((2*4, 4))
    for i in range(2*4):
      if i < 4:
        G[i,i] = 0.5*dt**2
      else:
        G[i,i-4] = dt
    self.Q = np.dot(np.dot(G,Q0), G.T)


    self.R = np.diag((1.0, 1.0, 1.0, 1.0)) * r_noise  # observation noise matrix
    self.lastResult = np.array([[0], [0], [0], [0], [0], [0], [0], [0]])

  def predict(self):
    """Predict state vector u and variance of uncertainty P (covariance).
            where,
            u: previous state vector
            P: previous covariance matrix
            F: state transition matrix
            Q: process noise matrix
        Equations:
            u'_{k|k-1} = Fu'_{k-1|k-1}
            P_{k|k-1} = FP_{k-1|k-1} F.T + Q
            where,
                F.T is F transpose
        Args:
            None
        Return:
            vector of predicted state estimate
        """
    # Predicted state estimate
    self.u = np.dot(self.F, self.u)
    # Predicted estimate covariance
    self.P = np.dot(self.F, np.dot(self.P, self.F.T)) + self.Q
    self.lastResult = self.u  # same last predicted result
    return self.u

  def correct(self, b, flag):
    """Correct or update state vector u and variance of uncertainty P (covariance).
        where,
        u: predicted state vector u
        A: matrix in observation equations
        b: vector of observations
        P: predicted covariance matrix
        Q: process noise matrix
        R: observation noise matrix
        Equations:
            C = AP_{k|k-1} A.T + R
            K_{k} = P_{k|k-1} A.T(C.Inv)
            u'_{k|k} = u'_{k|k-1} + K_{k}(b_{k} - Au'_{k|k-1})
            P_{k|k} = P_{k|k-1} - K_{k}(CK.T)
            where,
                A.T is A transpose
                C.Inv is C inverse
        Args:
            b: vector of observations
            flag: if "true" prediction result will be updated else detection
        Return:
            predicted state vector u
        """

    if not flag:  # update using prediction
      self.b = self.lastResult[0:4]
    else:  # update using detection
      self.b = b
    C = np.dot(self.A, np.dot(self.P, self.A.T)) + self.R
    K = np.dot(self.P, np.dot(self.A.T, np.linalg.inv(C)))

    self.u = self.u + np.dot(K, (self.b - np.dot(self.A, self.u)))
    self.P = self.P - np.dot(K, np.dot(C, K.T))
    self.lastResult = self.u
    return self.u[0:4]
