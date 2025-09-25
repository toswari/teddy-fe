import numpy as np

class KalmanFilter:
    def __init__(self, F, H, Q, R, P, x):
        """
        Initialize Kalman Filter
        
        Args:
            F: State transition model
            H: Observation model
            Q: Process noise covariance
            R: Observation noise covariance
            P: Initial error covariance
            x: Initial state estimate
        """
        self.F = F  # State transition model
        self.H = H  # Observation model
        self.Q = Q  # Process noise covariance
        self.R = R  # Observation noise covariance
        self.P = P  # Error covariance
        self.x = x  # State estimate
    
    def predict(self):
        """Prediction step"""
        # Predict state
        self.x = self.F @ self.x
        # Predict error covariance
        self.P = self.F @ self.P @ self.F.T + self.Q
    
    def update(self, z):
        """Update step with measurement z"""
        # Innovation
        y = z - self.H @ self.x
        # Innovation covariance
        S = self.H @ self.P @ self.H.T + self.R
        # Kalman gain
        K = self.P @ self.H.T @ np.linalg.inv(S)
        # Update state estimate
        self.x = self.x + K @ y
        # Update error covariance
        I = np.eye(self.P.shape[0])
        self.P = (I - K @ self.H) @ self.P
    
class RauchTungStriebelSmoother:
    def __init__(self, F, Q):
        """
        Initialize Rauch-Tung-Striebel (RTS) Smoother
        
        Args:
            F: State transition model
            Q: Process noise covariance
        """
        self.F = F
        self.Q = Q
        self.filtered_states = []
        self.filtered_covariances = []
        self.predicted_covariances = []
    
    def add_filtered_estimate(self, x_filtered, P_filtered, P_predicted):
        """Add filtered estimate from Kalman filter"""
        self.filtered_states.append(x_filtered.copy())
        self.filtered_covariances.append(P_filtered.copy())
        self.predicted_covariances.append(P_predicted.copy())
    
    def smooth(self):
        """Perform RTS smoothing on stored filtered estimates"""
        n = len(self.filtered_states)
        if n == 0:
            return [], []
        
        self.filtered_states = np.array(self.filtered_states)
        self.filtered_covariances = np.array(self.filtered_covariances)
        self.predicted_covariances = np.array(self.predicted_covariances)
        
        smoothed_states = np.zeros((n, self.filtered_states[0].shape[0]))
        smoothed_covariances = np.zeros((n, self.filtered_covariances[0].shape[0], self.filtered_covariances[0].shape[1]))
        
        # Initialize with last filtered estimate
        smoothed_states[-1] = self.filtered_states[-1].copy()
        smoothed_covariances[-1] = self.filtered_covariances[-1].copy()
        
        # Backward pass
        for k in range(n - 2, -1, -1):
            # Smoother gain
            A = self.filtered_covariances[k] @ self.F.T @ np.linalg.pinv(self.predicted_covariances[k + 1])
            
            # Smoothed state
            smoothed_states[k] = self.filtered_states[k] + A @ (smoothed_states[k + 1] - self.F @ self.filtered_states[k])
            
            # Smoothed covariance
            smoothed_covariances[k] = self.filtered_covariances[k] + A @ (smoothed_covariances[k + 1] - self.predicted_covariances[k + 1]) @ A.T
        
        return smoothed_states, smoothed_covariances
    
    def clear(self):
        """Clear stored estimates"""
        self.filtered_states.clear()
        self.filtered_covariances.clear()
        self.predicted_covariances.clear()