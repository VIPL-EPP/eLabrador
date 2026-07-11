import numpy as np
import time
from .tools import get_relative_angle
from .word_similiarity import SentenceSim
from collections import deque

class ObjectServo:
    def __init__(self,object_name:str='') -> None:
        self.object_name = object_name
        self.object_buffer = []
        self.object_stamp = time.perf_counter()
        self.sentence_sim = SentenceSim(vector_sim=False,tf_sim=True)
        self.POS_NEAR_THRESHOLD = 1 # meter
        self.OBJECT_MATCH_SIM_THRESHOLD = 0.5 # probability
        self.OBJECT_LIFE = 5

    def reset_object(self,object_name:str):
        self.object_name = object_name
        self.object_buffer = deque(maxlen=1)

    def update(self,objects:list):
        objects.sort(key=lambda obj: self.object_match(obj), reverse=True)
        if self.object_match(objects[0]) < self.OBJECT_MATCH_SIM_THRESHOLD:
            return False
        object_position = objects[0]['position']
        if self.check_object_buffer(object_position):
            self.object_buffer.append(objects[0])
            # self.object_buffer[0] = objects[0]

        return True
    
    def check_object_time(self):
        if time.perf_counter() - self.object_stamp > self.OBJECT_LIFE:
            self.object_buffer.clear()
            return False
        return True
    
    def pursuit_yaw(self,self_direction,self_location):
        if len(self.object_buffer)>2:
            print('detect two target')
            return None
        target_direction = np.array(self.object_buffer[0]['position']) - np.array(self_location)
        return np.degrees(get_relative_angle(self_direction,target_direction[:2]))

    def pursuit_pitch(self,self_direction,self_location):
        if len(self.object_buffer)>2:
            print('detect two target')
            return None
        target_direction = np.array(self.object_buffer[0]['position']) - np.array(self_location)
        target_direction = np.array([np.linalg.norm(target_direction[:2]) ,target_direction[2]])
        return np.degrees(get_relative_angle(self_direction,target_direction))

    def object_match(self,object):
        # return self.sentence_sim.vector_similarity(self.object_name,object['text'])
        return self.sentence_sim.tf_similarity(self.object_name,object['text'])
    
    def check_object_buffer(self, object_position):
        '''
        return True when the object is not found in buffer.
        '''
        if not self.object_buffer:
            return True
        self.object_stamp = time.perf_counter()
        for obj in self.object_buffer:
            if np.linalg.norm(object_position-obj['position'])>self.POS_NEAR_THRESHOLD:
                return True
        return False

