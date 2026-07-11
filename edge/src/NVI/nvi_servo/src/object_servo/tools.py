import numpy as np

def get_relative_angle(self_direction,target_direction):
    self_direction, target_direction = np.array(self_direction),np.array(target_direction)
    self_direction /= np.linalg.norm(self_direction)
    target_direction /= np.linalg.norm(target_direction)
    theta = np.arctan2(np.cross(self_direction,target_direction,),np.dot(self_direction,target_direction))
    return theta


