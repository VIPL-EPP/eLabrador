import numpy as np
from pykalman import KalmanFilter

class KalmanFilterLLA:
    '''
    function: Kalman filter for Longitude, Latitude, Altitude (under development)
    usage: kf = KalmanFilterLLA()
           kf.update(observation,time_stamp)
    comment: not used in the current version
    '''
    def __init__(self,measurement_noise_std=1e-4,process_noise_std=1e-4) -> None:
        self.transition_matrix = np.array([[1, 0, 1, 0],
                                  [0, 1, 0, 1],
                                  [0, 0, 1, 0],
                                  [0, 0, 0, 1]])
        self.observation_matrix = np.array([[1, 0, 0, 0],
                                    [0, 1, 0, 0]])
        self.observation_covariance = np.eye(2) * measurement_noise_std**2
        self.transition_covariance = np.eye(4) * process_noise_std**2
        self.initial_state_covariance = np.eye(4) * 1
        self.kf = None

    def init_filter(self,init_observations,init_time_stamp):
        self.initial_state_mean = [init_observations[0], init_observations[1], 0, 0]
        self.current_state = self.initial_state_mean
        self.init_time_stamp = init_time_stamp
        self.current_time_stamp = init_time_stamp
        self.current_covariance = self.initial_state_covariance
        self.kf = KalmanFilter(
            transition_matrices=self.transition_matrix,
            observation_matrices=self.observation_matrix,
            initial_state_mean=self.initial_state_mean,
            initial_state_covariance=self.initial_state_covariance,
            observation_covariance=self.observation_covariance,
            transition_covariance=self.transition_covariance
        )
    
    def update(self,observation,time_stamp):
        if self.kf is None:
            self.init_filter(observation,time_stamp)
            return observation[0],observation[1]
        dt = time_stamp-self.current_time_stamp
        self.kf.transition_matrices = np.array([[1, 0, dt, 0],
                                           [0, 1, 0, dt],
                                           [0, 0, 1, 0],
                                           [0, 0, 0, 1]])
        self.current_state, self.current_covariance = self.kf.filter_update(
            self.current_state, self.current_covariance, observation
        )
        return self.current_state[0],self.current_state[1]