"""
Env 2D
@author: huiming zhou
@modified author: lixuan
"""
import numpy as np

class Env:
    def __init__(self):
        self.x_range = 51  # size of background
        self.y_range = 31
        self.motions = [(-1, 0), (-1, 1), (0, 1), (1, 1),
                        (1, 0), (1, -1), (0, -1), (-1, -1)]
        self.obs = self.obs_map()
        self.map = np.zeros((self.x_range,self.y_range),dtype=np.int8)

    def update_obs(self, obs):
        self.obs = obs

    #modified by lixuan
    def obs_map_set(self,size,map):
        self.x_range, self.y_range = size
        self.obs = set()
        self.map = map
        for i in range(self.x_range):
            for j in range(self.y_range):
                if map[i][j] > 90: # error # changed by lixuan from 1 to 50
                    self.obs.add((i,j))
        
    def obs_map(self):
        """
        Initialize obstacles' positions
        :return: map of obstacles
        """

        x = self.x_range
        y = self.y_range
        obs = set()

        for i in range(x):
            obs.add((i, 0))
        for i in range(x):
            obs.add((i, y - 1))

        for i in range(y):
            obs.add((0, i))
        for i in range(y):
            obs.add((x - 1, i))

        for i in range(10, 21):
            obs.add((i, 15))
        for i in range(15):
            obs.add((20, i))

        for i in range(15, 30):
            obs.add((30, i))
        for i in range(16):
            obs.add((40, i))

        return obs
