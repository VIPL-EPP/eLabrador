import os
import numpy as np
import math
from .map_draw import *
from .semantic_config import *
from .Astar import AStar
from .env import Env
import time
import itertools
import torch
import torch.nn as nn
from PIL import Image
import random
import jsonlines
# from .RSSM import RSSM, Simplified_RSSM
from scipy.ndimage import distance_transform_edt

class Human_MLP(nn.Module):
    '''
    MLP model for human motion prediction

    Args:
        path_size (int): The path size of the model
        action_size (int): The action size of the model
        hidden_size (int): The hidden size of the model
        output_size (int): The output size of the model
    '''
    def __init__(self, path_size, action_size, hidden_size, output_size):
        super(Human_MLP, self).__init__()
        self.path_size = path_size
        # Encode the path
        self.path_model = nn.Sequential(
            nn.Linear(path_size, hidden_size), nn.ReLU(),
            nn.Linear(hidden_size, hidden_size), nn.ReLU(),
        )
        # Encode the action
        self.action_model = nn.Sequential(
            nn.Linear(action_size, hidden_size), nn.ReLU()
        )
        # Predict the future path
        self.pred_model = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size), nn.ReLU(),
            nn.Linear(hidden_size, output_size)
        )

    def forward(self, x):
        path = x[:, :self.path_size]
        action = x[:, self.path_size:]
        path_feature = self.path_model(path)
        action_feature = self.action_model(action)

        x = torch.cat([path_feature, action_feature], dim=1)
        x = self.pred_model(x)
        return x

class LocalPlanner:
    '''
    class for local planning

    map format: 2D grid map data with (height, width) shape.

    all input points are based on world map in meters.

    drawing: x:  control the second (width) dimension; y: control the first dimension.
    '''
    def __init__(self):
        self.map_data = np.zeros((0,0),dtype=np.int8)
        self.map_data_visualize = np.zeros((0, 0), dtype=np.int8)
        self.map_data_pr = np.zeros((0, 0), dtype=np.int8)
        self.instruction = [1, 1, 1]
        # model_path = os.path.expanduser(
        #     os.environ.get(
        #         'NVI_LOCAL_PLANNING_MODEL',
        #         os.path.join(os.path.dirname(__file__), 'finetuned_model_15_1layer_0.pth')
        #     )
        # )
        # if not os.path.exists(model_path):
        #     raise FileNotFoundError(
        #         'Local planning model is missing. Set NVI_LOCAL_PLANNING_MODEL to '
        #         'finetuned_model_15_1layer_0.pth or place the file next to local_planner.py.'
        #     )
        self.given_path = [
            (100/10, 100/10),
            # (280/10, 100/10),
            # (280/10, 400/10),
            (400/10, 400/10)
            # (800/20, 300/20),
            # (900/20, 380/20),
            # (900/20, 900/20)
        ]
        self.terminal = [400/10, 400/10]
        # image_array = np.array(image)
        # self.pre_difined_map = np.where(image_array == 255, 0, 50)
        # Load the serialized model weights.
        # state_dict = torch.load(model_path, map_location=torch.device('cpu'))

        # Build the predictor model instance dynamically.
        # self.predict_model = Simplified_RSSM()
        # self.predict_model.load_state_dict(state_dict)
        self.best_route = []
        # Switch the predictor into evaluation mode.
        # self.predict_model.eval()
        # map
        self.map_width = 0
        self.map_height = 0
        self.map_resolution = 0 
        self.map_origin = (0,0)
        # self.map_width = self.pre_difined_map.shape[0]
        # self.map_height = self.pre_difined_map.shape[1]
        # position
        self.location = None
        self.direction = None
        self.path = []
        self.target_direction = None
        self.target = None
        self.location_list = []
        self.pose_list = []
        # self.location_list = [[10, 10], [10.6, 10], [11.2, 10], [11.8, 10]]
        # line
        self.target_path = [] # in meter, for line following
        # self.target_path = self.generate_intermediate_points(interval=0.5)
        # time stamp
        self.map_stamp = time.perf_counter()
        self.location_stamp = time.perf_counter()
        self.direction_stamp = time.perf_counter()
        self.target_direction_stamp = time.perf_counter()
        self.target_path_stamp = time.perf_counter()
        # parameter
        self.SECTOR_NUM = 12
        # set predifined map
        # self.set_predifined_map()

    @staticmethod
    def distance(p1, p2):
        return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

    
    def generate_intermediate_points(self, interval=5):
        intermediate_points = []
        for i in range(len(self.given_path)-1):
            p1 = self.given_path[i]
            p2 = self.given_path[i+1]
            dist = self.distance(p1, p2)
            direction = ((p2[0]-p1[0])/dist, (p2[1]-p1[1])/dist)

            num_points_between = int(dist // interval)
            for j in range(1, num_points_between + 1):
                new_point = (int(p1[0] + j*interval*direction[0]), int(p1[1] + j*interval*direction[1]))
                if new_point not in intermediate_points:
                    intermediate_points.append(new_point)
        return intermediate_points 
    
    def set_map(self, map_data, map_resolution,map_origin):
        self.map_stamp = time.perf_counter()
        self.map_data = map_data
        self.map_height,self.map_width = self.map_data.shape
        self.map_resolution = map_resolution
        self.map_origin = map_origin
        # print(self.map_origin, self.map_resolution, self.map_width, self.map_height)

    
    def set_predifined_map(self):
        self.map_stamp = time.perf_counter()
        self.map_data = self.pre_difined_map
        self.map_height,self.map_width = self.map_data.shape
        self.map_resolution = 0.2
        self.map_origin = (0, 0)
    
    def add_height_map(self,height_map_data):
        '''
        need to be invoked after set_map()
        '''
        if self.map_data.size <=0:
            raise ValueError("Local map is not initialized.")
        self.map_data[height_map_data>0] = 100 # add obstacle.
    
    def set_semantic_map(self, map_data, map_resolution, map_origin):
        self.map_data_smantic = map_data
        self.map_height_semantic, self.map_width_semantic = self.map_data.shape
        self.map_resolution_semantic = map_resolution
        self.map_origin_semantic = map_origin

    def update_local_status(self, pose):
        '''
        location: (xi, yi)
        direction: (xi, yi)
        # path: [ (xi, yi, zi) ]
        ''' 
        self.location,self.direction = pose
        self.location_stamp = time.perf_counter()
        self.direction_stamp = self.location_stamp
        # if len(self.path) > 10: # !-----------------------------------------------------!
        #     self.direction = np.array(self.path[-1]) - np.array(self.path[0])
        # print(self.location,self.direction)
    
    def update_global_status(self,target_direction,target_distance=10):
        '''
        target_degree: (xi, yi)
        '''
        # TODO timestamp align
        # direction = self_direction
        # if self_direction is None:
        #     if self.direction is None:
        #         raise ValueError("Self direction is not initialized.") 
        #     direction  = (self.direction[0],self.direction[1])
        self.target_direction_stamp = time.perf_counter()
        self.target_direction = target_direction
        # self.target_direction = self.point2d_rotation(direction, np.deg2rad(-target_degree))
    
    def update_time_stamp(self,MAP_LIFE=60,POS_LIFE=10,PATH_LIFE=30):
        time_now = time.perf_counter()
        if time_now - self.map_stamp > MAP_LIFE:
            self.map_data = np.zeros((0,0),dtype=np.int8)
            self.map_stamp = time_now
        if time_now - self.location_stamp > POS_LIFE:
            self.location = None
            self.location_stamp = time_now
        if time_now - self.direction_stamp > POS_LIFE:
            self.direction = None
            self.direction_stamp = time_now
        if time_now - self.target_direction_stamp > POS_LIFE:
            self.target_direction = None
            self.target_direction_stamp = time_now
        if time_now - self.target_path_stamp > PATH_LIFE:
            self.target_path = []
            self.target_path_stamp = time_now
            
    
    def draw_target(self,radius=3):
        if self.target is None:
            print("GPS  initilizing...")
            return
        target = ((np.array(self.target) - np.array(self.map_origin)
                     )/self.map_resolution).astype(int)
        draw_point(self.map_data_visualize, (target[0], target[1]), radius)

    def draw_target_direction(self, length=5):
        if self.target_direction is None:
            raise ValueError("Target direction is not initialized.")
        location = (self.location[0], self.location[1])
        location = ((np.array(location) - np.array(self.map_origin)) /
                    self.map_resolution).astype(int)
        self.map_data_visualize = draw_arrow(self.map_data_visualize,
                   (location[0], location[1]), self.target_direction, length,color=50).astype(np.int8)
        
    def draw_location(self, position, direction, radius = 3, length = 7):
        # location = (self.location[0], self.location[1])
        location = ((np.array(position) - np.array(self.map_origin))/self.map_resolution).astype(int)
        print(location)
        self._draw_circle(self.map_data_visualize, tuple(location), radius)
        # Draw an arrow based on the location and direction
        end_point = (location[0] + int(length * direction[0]), location[1] + int(length * direction[1]))
        self._draw_line(self.map_data_visualize, tuple(location), end_point, color=60)

    def draw_path(self, waypoints, color = -128):
        for i in range(len(waypoints)-1):
            waypoint = waypoints[i]
            next_waypoint = waypoints[i+1]
            start = ((np.array(waypoint) - np.array(self.map_origin))/self.map_resolution).astype(int)
            end = ((np.array(next_waypoint) - np.array(self.map_origin))/self.map_resolution).astype(int)
            # print(start, end)
            self._draw_line(self.map_data_visualize, tuple(start), tuple(end), color) 
    
    # def draw_target_path(self, path):
    #     for item in path:
    #         location = ((np.array(item))/self.map_resolution).astype(int)
    #         self.map_data_visualize[location[0]][location[1]] = 127
    #         # print(path[0], path[1])
    #         # if item == path[-1]:
    #             # self.map_data_visualize[location[0]][location[1]] = -100

    def _draw_circle(self, map_data, center, radius):
        """
        Draw a circle on the map data.

        Args:
            map_data (np.ndarray): The map data to draw on.
            center (tuple): The center of the circle (x, y).
            radius (int): The radius of the circle.
        """
        x0, y0 = center
        # Accept either grid indices or world coordinates for the circle center.
        # Treat floating-point values or out-of-range values as world coordinates.
        is_world_coord = False
        if isinstance(x0, float) or isinstance(y0, float):
            is_world_coord = True
        if (x0 < 0 or y0 < 0 or
            x0 >= map_data.shape[1] or y0 >= map_data.shape[0]):
            is_world_coord = True

        if is_world_coord:
            # Convert world coordinates in meters to map grid indices.
            world_center = np.array([x0, y0])
            grid_center = ((world_center - np.array(self.map_origin)) /
                           self.map_resolution).astype(int)
            x0, y0 = int(grid_center[0]), int(grid_center[1])
        else:
            # The input is already expressed as grid indices.
            x0, y0 = int(x0), int(y0)

        for y in range(-radius, radius + 1):
            for x in range(-radius, radius + 1):
                if x**2 + y**2 <= radius**2:
                    if 0 <= y0 + y < map_data.shape[0] and 0 <= x0 + x < map_data.shape[1]:
                        map_data[y0 + y, x0 + x] = 127

    def _draw_line(self, map_data, start, end, color):
        """
        Draw a line on the map data using Bresenham's algorithm.

        Args:
            map_data (np.ndarray): The map data to draw on.
            start (tuple): The starting point of the line (x, y).
            end (tuple): The ending point of the line (x, y).
            color: The color of the line.
        """
        x1, y1 = start
        x2, y2 = end
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= y1 < map_data.shape[0] and 0 <= x1 < map_data.shape[1]:
                map_data[y1, x1] = color
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy
    
    def draw_target_path(self):
        if not self.target_path:
            raise ValueError("Targt path is not initialized.")
        is_begin_marked = False
        for target_location in self.target_path:
            target_location = ((np.array(target_location) - np.array(self.map_origin)) /
                    self.map_resolution)
            target_location = (round(target_location[0]),round(target_location[1]))
            if not is_begin_marked:
                if target_location[1] >=0 and target_location[1]<self.map_width and target_location[0] >=0 and target_location[0]<self.map_height:
                    self.map_data_visualize[target_location[1]][target_location[0]] = -100
                is_begin_marked = True
                continue
            if target_location[1] >=0 and target_location[1]<self.map_width and target_location[0] >=0 and target_location[0]<self.map_height:
                self.map_data_visualize[target_location[1]][target_location[0]]=127
    #             self.map_data_visualize[target_location[1]][target_location[0]+1]=127
    #             # self.map_data_visualize[target_location[1]][target_location[0]+2]=127
    #             self.map_data_visualize[target_location[1]+1][target_location[0]]=127
    #             self.map_data_visualize[target_location[1]+1][target_location[0]+1]=127
    #             # self.map_data_visualize[target_location[1]+2][target_location[0]+1]=127
    #             # self.map_data_visualize[target_location[1]+1][target_location[0]+2]=127
    #             # self.map_data_visualize[target_location[1]+2][target_location[0]+2]=127
    #             # self.map_data_visualize[target_location[1]+2][target_location[0]]=127

    
    def draw_best_route(self):
        if self.best_route is None:
            raise ValueError("Best route is not initialized.")
        for location in self.target_path[0:6]:
            location = ((np.array(location) - np.array(self.map_origin)) /
                    self.map_resolution)
            location = (round(location[0]+random.randint(-2, 2)),round(location[1])+random.randint(-2, 2))
            if location[1] >=0 and location[1]<self.map_width and location[0] >=0 and location[0]<self.map_height:
                self.map_data_visualize[location[1]][location[0]] = 150

    def draw_obstacle(self,obstacle_threahold=80):
        self.map_data_visualize[self.map_data_visualize>=obstacle_threahold] = 100
        
    def draw_coordinate_origin(self):
        '''
        draw the origin of the coordinate, the bias is the x direction (right).
        '''
        self.map_data_visualize[0][1] = 110

    def obstacle_detect(self,location,max_scan):
        '''
       input:  location: (x, y); max_scan: maximum scan distance.
       return: the nearest obstacles distance in self.SECTOR_NUM sectors.
        '''
        x_loc , y_loc = ((np.array(location) -np.array(self.map_origin))/self.map_resolution).astype(int)
        max_scan = int(max_scan/self.map_resolution)

        obstacles = [-1]*self.SECTOR_NUM
        obstacles_semantic = [None]*self.SECTOR_NUM

        x_start = x_loc - max_scan if x_loc - max_scan >= 0 else 0
        y_start = y_loc - max_scan if y_loc - max_scan >= 0 else 0
        x_end = x_loc + max_scan if x_loc + max_scan <= self.map_width else self.map_width
        y_end = y_loc + max_scan if y_loc + max_scan <= self.map_height else self.map_height

        for y in range(y_start,y_end):
            for x in range(x_start,x_end):
                map_value = (self.map_data[y][x]+256)%256
                if map_value > 50 and map_value<255:
                    radius = np.linalg.norm(np.array([y_loc - y, x_loc - x]))
                    if radius > 1e-6:
                        sector_id = self.get_sector_id((y_loc-y, x_loc - x))
                        if obstacles[sector_id] < 0 or obstacles[sector_id]>radius:
                            obstacles[sector_id]  = radius
                            obstacles_semantic[sector_id] = COLOR_VOICE[map_value]
                        # else:
                        #     if 
                        #     obstacles[sector_id] = min(obstacles[sector_id],radius)
        for i in range(len(obstacles)):
            obstacles[i]*=self.map_resolution
        return obstacles,obstacles_semantic

    @staticmethod
    def point2d_rotation(point,theta):
        '''
        point: (x, y); theta: rad
        '''
        x, y = point
        x_ = x * math.cos(theta) + y * math.sin(theta)
        y_ = - x*math.sin(theta) + y * math.cos(theta)
        return (x_,y_)
    
    @staticmethod
    def cosine_distance(vector1, vector2):
        vector1=np.array(vector1)
        vector2=np.array(vector2)
        return np.dot(vector1, vector2) / (np.linalg.norm(vector1) * np.linalg.norm(vector2))

    def get_sector_id(self,direction):
        '''
        input: direction: a direction represention vector, direction matters.

        return: the sector id of input direction.
        '''
        x, y = direction
        trans_theta = np.deg2rad(180/self.SECTOR_NUM)
        x,y = self.point2d_rotation((x,y),trans_theta)
        # x, y = x * math.cos(trans_theta) + y * math.sin(trans_theta), -x*math.sin(trans_theta) + y * math.cos(trans_theta)
        radius = np.linalg.norm(np.array([x,y]))
        theta = np.rad2deg(math.acos(y/radius))
        if y>0:
            theta = theta if x >= 0 else 360 - theta
        else:
            theta =  theta if x>0 else 360 - theta
        return int(theta * self.SECTOR_NUM / 360)
    
    def search_ray(self,location,direction,length=3):
        '''
        return: the smantic in searched direction
        '''
        # location = (self.location[0], self.location[1])
        start = ((np.array(location) - np.array(self.map_origin_semantic)) /
                    self.map_resolution_semantic).astype(int)
        direction = np.array(direction)
        end = start+(length*direction /
                     (self.map_resolution_semantic*np.linalg.norm(direction))).astype(int)
        semantic_value,distance = bresenham_line_search(self.map_data_smantic,start,end)
        distance *= self.map_resolution
        if semantic_value == COLOR_GRIDMAP['flat']:
            distance = length
        # print(semantic_value)
        return (COLOR_VOICE[semantic_value],distance)

        
    def get_cmd(self):
        '''
        return: obstacle avoidacne command
        '''
        if self.location is None or self.direction is None:
            print("self location/direction initilizing....")
            return
        _mode = 'L'
        _action = '|'
        _description = '|'
        forward_view = self.search_ray(
            (self.location[0], self.location[1]), (self.direction[0], self.direction[1]), 3)
        obstacles,obstacles_semantic = self.obstacle_detect((self.location[0],self.location[1]), 3)
        current_sector_id = self.get_sector_id((self.direction[0],self.direction[1]))
        if forward_view[0] == COLOR_VOICE[0] or obstacles[current_sector_id] < 0:
            _action += '直行'
            _description += '前方路面直行'
            return _mode+_action+_description

        _description += obstacles_semantic[current_sector_id]

        left_sector_id = (current_sector_id + self.SECTOR_NUM - (int)(self.SECTOR_NUM / 4)) % self.SECTOR_NUM
        right_sector_id = (current_sector_id + (int)(self.SECTOR_NUM / 4)) % self.SECTOR_NUM
        left_blank, right_blank = 0, 0
        sector_id =left_sector_id
        while  sector_id != current_sector_id:
            left_blank += 1 if obstacles[sector_id]<0 else 0
            sector_id = (sector_id +1)%self.SECTOR_NUM
        sector_id = right_sector_id
        while sector_id != current_sector_id:
            right_blank += 1 if obstacles[sector_id]<0 else 0
            sector_id = (sector_id - 1)%self.SECTOR_NUM
   
        if obstacles[current_sector_id]>0 and obstacles[current_sector_id] <3:
            _mode = 'M'
            if right_blank == 0 and right_blank ==0:
                _mode = 'H'
                _action += '停止'
            else:
                _action += '右转' if right_blank>left_blank else '左转'
        return _mode+_action+_description

    def get_objects(self,location,direction):
        '''
        return: surrounding obstacles
        '''
        if self.map_data_smantic.size <=0:
            raise ValueError("Local map is not initialized.")
        objects = []
        location = (location[0], location[1])
        direction = (direction[0], direction[1])
        # forward_view = self.search_ray(location, direction, 3)
        # objects.append((forward_view[0],0,forward_view[1]))
        sector_start = int(self.SECTOR_NUM/4)
        for sector_id in range(sector_start, -sector_start-1, -1):
            trans_theta = np.deg2rad(sector_id*30)
            direction_ = self.point2d_rotation(direction,trans_theta) #self.point2d_rtarget_directionotation(direction, trans_theta)
            sector_view = self.search_ray(location, direction_, 3)
            objects.append((sector_view[0], -sector_id, sector_view[1]))
        return objects

    def path_search(self):
        # Use the adjusted road direction vector and extend it to the map boundary as the A* target.
        if self.location is None:
            raise ValueError("Self location is not initialized.")
        if self.target_direction is None:
            raise ValueError("Target direction is not initialized.")
        if self.map_data.size <=0:
            raise ValueError("Local map is not initialized.")
        location,target_direction = (self.location[0],self.location[1]),self.target_direction
        map_origin, map_data  = self.map_origin, self.map_data.copy()
        # print(self.target_direction)

        # location parse
        loc_x, loc_y = location[0], location[1]
        loc_x_grid = (loc_x-map_origin[0])/self.map_resolution
        loc_y_grid = (loc_y-map_origin[1])/self.map_resolution
        # target direction parse
        dir_x, dir_y = target_direction[0], target_direction[1]
        dir_len = (dir_x**2 + dir_y**2) ** 0.5
        if dir_len < 1e-6:
            raise ValueError("Target direction has near-zero length.")
        dir_x, dir_y = dir_x / dir_len, dir_y / dir_len
        

        # Compute the ray intersection with the map boundary in grid coordinates.
        height, width = self.map_height, self.map_width
        t_candidates = []

        # Intersections with the x boundaries.
        if abs(dir_x) > 1e-6:
            if dir_x > 0:
                t_x = ((width - 1) - loc_x_grid) / dir_x
            else:
                t_x = (0.0 - loc_x_grid) / dir_x
            if t_x > 0:
                t_candidates.append(t_x)

        # Intersections with the y boundaries.
        if abs(dir_y) > 1e-6:
            if dir_y > 0:
                t_y = ((height - 1) - loc_y_grid) / dir_y
            else:
                t_y = (0.0 - loc_y_grid) / dir_y
            if t_y > 0:
                t_candidates.append(t_y)

        # Return failure if this direction never reaches the map boundary.
        if not t_candidates:
            return False

        t_min = min(t_candidates)
        target_x_grid = loc_x_grid + dir_x * t_min
        target_y_grid = loc_y_grid + dir_y * t_min

        # Round and clamp the target to valid grid indices.
        target_x_idx = int(round(target_x_grid))
        target_y_idx = int(round(target_y_grid))
        target_x_idx = max(0, min(width - 1, target_x_idx))
        target_y_idx = max(0, min(height - 1, target_y_idx))

        # Finalize the start and target grid cells.
        start_point = (int(round(loc_y_grid)), int(round(loc_x_grid)))
        target_point = (target_y_idx, target_x_idx)

        # need to be more clear
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7,7)) # 7*0.2 = 1.4m
        c0 = map_data<0
        map_data[c0]=0 # set the unexplored area to 0
        c1 = map_data>0
        map_data = cv2.dilate(map_data.astype(np.uint8), kernel)
        c2 = map_data>0
        c = np.logical_xor(c1,c2)
        map_data[c]=20
        map_data[c0] = 50 # It is hard to say the unexplored area is good or not. 

        # ====== Add the historical path retention term here ======
        # Convert the previous-frame path into grid coordinates.
        prev_path_grid = None
        if len(self.target_path) > 0:
            prev_path_grid = []
            for p in self.target_path:
                gx = int((p[0] - map_origin[0]) / self.map_resolution)
                gy = int((p[1] - map_origin[1]) / self.map_resolution)
                prev_path_grid.append((gy, gx))

        if prev_path_grid is not None and len(prev_path_grid) > 0:
            # 1) Build a boolean mask: True means not on the previous path, False means on the previous path.
            prev_mask = np.ones_like(map_data, dtype=bool)
            for (py, px) in prev_path_grid:
                if 0 <= py < self.map_height and 0 <= px < self.map_width:
                    prev_mask[py, px] = False  # Mark previous-path cells as False.

            # 2) Compute a distance transform to the previous path set, in grid cells.
            dist_map = distance_transform_edt(prev_mask).astype(np.float32)

            # 3) Convert grid distance to meters for easier tuning.
            dist_map *= self.map_resolution   # Convert the grid distance to meters.

            # 4) Cap the influence range; cells beyond 2 meters are treated the same.
            max_influence = 2.0   # Influence radius in meters; tune as needed.
            dist_clipped = np.minimum(dist_map, max_influence)

            # 5) Build the retention cost map: larger distance adds more cost.
            lambda_dev = 10.0  # Retention-term weight lambda; tune as needed.
            dev_cost = (lambda_dev * dist_clipped / max_influence)

            # 6) Add the cost to map_data with clipping to avoid uint8 overflow.
            map_data = map_data.astype(np.float32)
            map_data += dev_cost
            map_data = np.clip(map_data, 0, 255).astype(np.uint8)
        # ====== End of historical path retention term ======
        envinfo = Env()
        
        envinfo.obs_map_set(self.map_data.shape, map_data)

        astar = AStar(target_point, start_point, "euclidean", envinfo=envinfo, alpha=3)

        try:
            path, cost_s = astar.searching()
        except Exception:
            return False
        
        # Convert path grid points back to world coordinates.
        self.target_path = []
        for x, y in path[:-1]:
            real_y = x * self.map_resolution + map_origin[1]
            real_x = y * self.map_resolution + map_origin[0]
            self.target_path.append((real_x, real_y))

        if not self.target_path:
            return False
        return True

        

    def pure_pursuit(self,location,direction):
        '''
        location: (x, y) meter
        direction: (x,y) 
        '''
        if not self.target_path:
            raise ValueError("Targt path is not initialized.")
        p2path = [(location[0]-point[0])**2 + (location[1]-point[1])**2 for point in self.target_path] 
        idx = np.argmin(p2path)
        length  = len(self.target_path)
        next_direction = None
        if length - idx >10:
            idx  +=10
        else:
            idx = length -1 
        next_direction = np.array((self.target_path[idx][0] - location[0], self.target_path[idx][1] - location[1]))
        direction = np.array(direction)
        direction /= np.linalg.norm(direction)
        next_direction /= np.linalg.norm(next_direction)
        theta = np.arctan2(np.cross(direction,next_direction,),np.dot(direction,next_direction))
        return np.degrees(theta)

    def pure_pursuit_with_dis(self,location,direction,ahead_distance=0.5):
        '''
        location: (x, y) meter
        direction: (x,y) 
        '''
        if not self.target_path:
            raise ValueError("Targt path is not initialized.")
        p2path = [(location[0]-point[0])**2 + (location[1]-point[1])**2 for point in self.target_path] 
        idx = np.argmin(p2path)
        length  = len(self.target_path)
        raster_ahead_distance =  int(ahead_distance/self.map_resolution)
        next_direction = None
        if length - idx >raster_ahead_distance:
            idx  += raster_ahead_distance
            while idx+1<length:
                if p2path[idx+1]>=ahead_distance:
                    break
                idx += 1
        else:
            idx = length -1 
        next_direction = np.array((self.target_path[idx][0] - location[0], self.target_path[idx][1] - location[1]))
        direction = np.array(direction)
        direction /= np.linalg.norm(direction)
        next_direction /= np.linalg.norm(next_direction)
        theta = np.arctan2(np.cross(direction,next_direction,),np.dot(direction,next_direction))
        return np.degrees(theta)
    
    def pure_pursuit_with_obstacle_avoidance(self,location,direction,ahead_distance=2):
        '''
        location: (x, y) meter
        direction: (x,y) 
        '''
        if not self.target_path:
            raise ValueError("Targt path is not initialized.")
        target_path = self.target_path
        p2path = [(location[0]-point[0])**2 + (location[1]-point[1])**2 for point in target_path] 
        idx = np.argmin(p2path)
        length  = len(target_path)
        raster_ahead_distance =  int(ahead_distance/self.map_resolution)
        while  True:
            if length - idx >raster_ahead_distance:
                idx  += raster_ahead_distance
            while idx+1<length:
                if p2path[idx+1]>=ahead_distance:
                    break
                idx += 1
            else:
                idx = length -1
            collision, value, ahead_distance = self.check_collision(location,target_path[idx])
            if not collision:
                break
            if ahead_distance < 0.5:
                print('block.')
                return None
            # print('collison in ',ahead_distance)
            raster_ahead_distance =  int(ahead_distance/self.map_resolution)
        next_direction = np.array((target_path[idx][0] - location[0], target_path[idx][1] - location[1]))
        direction = np.array(direction)
        direction /= np.linalg.norm(direction)
        next_direction /= np.linalg.norm(next_direction)
        theta = np.arctan2(np.cross(direction,next_direction,),np.dot(direction,next_direction))
        return np.degrees(theta)

    def calculate_following_cost(self, location):
        shortest = 1e9
        point = 0
        # print(self.target_path)
        for i in range(1, len(self.target_path)):
            dx, dy = self.target_path[i][0] - self.target_path[i-1][0], self.target_path[i][1] - self.target_path[i-1][1]
            dx0, dy0 = location[0] - self.target_path[i][0], location[1] - self.target_path[i][1]
            dot_product = dx*dx0 + dy*dy0
            len_seq = dx**2 + dy**2
            if len_seq != 0:
                t = np.abs(dot_product/len_seq)
            else:
                t = 0
            shortest = min(shortest, t)
            if t < shortest:
                point = i
                shortest = t
        return shortest, point
    

    def imagine(self, obs_seq_feats, action_seq, num_imagine_steps=5):
        '''
        obs_seq_feats: (T, feature_length)
        action_seq: (T, 3)
        '''
        # random shooting

        # Define action representationsprint
        actions = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        # Enumerate all possible action combinations for the next 5 time steps
        future_action_combinations = list(itertools.product(actions, repeat=5))
        obs_seq_feats_batch = np.tile(obs_seq_feats, (len(future_action_combinations), 1, 1))
        combination_action_seqs = []
        for combination in future_action_combinations:
            # Here you can add code to process each action combination
            combined_action_seq = np.concatenate([action_seq, combination])
            combination_action_seqs.append(combined_action_seq)
        combined_action_seq = np.stack(combination_action_seqs, axis=0)
        # for item in combined_action_seq:
        #     print(item)
        input_feature = torch.tensor(obs_seq_feats_batch, dtype=torch.float32)
        action_sequence = torch.tensor(combined_action_seq, dtype=torch.float32)
        # print(action_sequence)
        output = self.predict_model.imagine(input_feature, action_sequence, num_imagine_steps)
        

        return output

    def point_to_segment_distance(self, p, a, b):
        # Vector from point p to the start of the segment
        ab = b - a
        ap = p - a
        ap_ap = np.dot(ap, ab)
        ab_sq = np.dot(ab, ab)

        if ab_sq == 0:
            return np.linalg.norm(ap)
        r = ap_ap / ab_sq
        if r < 0:
            return np.linalg.norm(ap)
        elif r > 1:
            return np.linalg.norm(p - b)
        else:
            projection = a + r * ab
            return np.linalg.norm(p - projection)

    def calculate_path_distance(self, path1, path2):
        total_distance = 0
        for point in path1:
            min_distance = float('inf')
            for i in range(len(path2) - 1):
                a = path2[i]
                b = path2[i + 1]
                distance = self.point_to_segment_distance(point, a, b)
                min_distance = min(min_distance, distance)
            total_distance += min_distance
        return total_distance/len(path1)
    def select_path(self, path_list, target_path):
        # print(target_path)
        # ((np.array(waypoint) - np.array(self.map_origin))/self.map_resolution).astype(int)
        actions = [[0, 0, 1], [0, 1, 0], [1, 0, 0]]

        # Enumerate all possible action combinations for the next 5 time steps
        future_action_combinations = list(itertools.product(actions, repeat=5))
        future_action_combinations = [
            combo for combo in future_action_combinations 
            if combo.count([0, 0, 1]) + combo.count([0, 1, 0]) <= 5
        ]
        actual_target_path = []
        for waypoint in target_path:
            actual_waypoint = np.array(waypoint)*self.map_resolution + np.array(self.map_origin)
            actual_target_path.append(actual_waypoint)
        scores = []
        t = []
        for path in path_list:
            index = len(t)
            t.append(1)
            action_sequence = future_action_combinations[index]
            count = sum(1 for lst in action_sequence if lst==[1, 0, 0])
            path_distance = self.calculate_path_distance(path, actual_target_path)
            smoothness = 0
            collision = False
            for i in range(1, len(path)-1):
                vec1 = path[i] - path[i-1]
                vec2 = path[i+1] - path[i]
                start  = path[i] - np.array(self.map_origin)
                end = path[i-1] - np.array(self.map_origin)
                # print(start, end)
                collision, _, _ = self.check_collision(start, end)
                angle = np.arccos(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
                smoothness += angle
            smoothness = smoothness/(len(path)-2)
            final_distance = np.linalg.norm(path[-1] - actual_target_path[-1])
            # print(np.linalg.norm(path[0] - actual_target_path[-1]))
            # print(collision)
            score = 1 * path_distance + 0 * smoothness + 2 * final_distance - 1 * count + 100 * collision
            # print(path_distance, smoothness, final_distance, count)
            # print(score, path_distance, smoothness, final_distance)
            scores.append(score)
        top_k_indices = np.argsort(scores)[:5]
        scores = [scores[i] for i in top_k_indices]
        # print(scores)
        return [path_list[i] for i in top_k_indices], [future_action_combinations[i] for i in top_k_indices], scores

    def select_best_action(self, action_list, future_positions, target_path):
        actual_target_path = []
        for waypoint in target_path:
            # actual_waypoint = np.array(waypoint)*self.map_resolution + np.array(self.map_origin)
            # actual_target_path.append(actual_waypoint)
            actual_target_path.append(np.array(waypoint))
        # print(actual_target_path)
        scores = []
        t = []
        for path in future_positions:
            index = len(t)
            t.append(1)
            action_sequence = action_list[index]
            count = sum(1 for lst in action_sequence if lst=='forward')
            path_distance = self.calculate_path_distance(path, actual_target_path)
            smoothness = 0
            collision = False

            # The unused cosine term below was left from development and is intentionally omitted.
            # idx = 0
            # min = 1e9
            # for j in range(0, len(target_path)):
            #     distance = np.linalg.norm(path[-1] - target_path[j])
            #     if distance < min:
            #         min = distance
            #         idx = j
            # target_vec = np.array([target_path[idx][0] - target_path[-1][0], target_path[idx][1] - target_path[-1][1]])
            # current_vec = path[-2] - path[-1]
            # # Heading consistency computation
            # if np.linalg.norm(target_vec) == 0:
            #     cos = 1
            # else:
            #     cos = np.dot(target_vec, current_vec)/(np.linalg.norm(target_vec)*np.linalg.norm(current_vec))
            # # print(target_vec, current_vec)

            for i in range(1, len(path)-1):
                vec1 = path[i] - path[i-1]
                vec2 = path[i+1] - path[i]
                start  = path[i] - np.array(self.map_origin)
                end = path[i-1] - np.array(self.map_origin)
                # print(start, end)
                collision, _, _ = self.check_collision(start, end)
                angle = np.arccos(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
                smoothness += angle
            smoothness = smoothness/(len(path)-2)
            if len(actual_target_path) != 0:
                final_distance = np.linalg.norm(path[-1] - actual_target_path[-1])
            else:
                return
            # print(np.linalg.norm(path[0] - actual_target_path[-1]))
            # print(collision)
            # print(path_distance, final_distance, count)
            # danger = 0
            # binary_map = np.array(self.map_data, dtype=bool)
            # free_dist = distance_transform_edt(~binary_map)
            # for point in path:
            #     x, y = int(point/self.map_resolution)
            #     danger += 1/(free_dist[x][y]+1)
            score = 0.5 * path_distance + 1 * final_distance - 3 * count + 100 * collision
            # print(path_distance, smoothness, final_distance, count)
            # print(score, path_distance, smoothness, final_distance)
            scores.append(score)
        # print(scores)
        best_index = np.argmin(scores)
        # print(scores[best_index])
        # print(scores, action_list)
        # sample 6 points in target_path
        if len(actual_target_path) > 6:
            step = len(actual_target_path) // 5
            sampled_target_path = [actual_target_path[i] for i in range(0, len(actual_target_path), step)][:6]
        else:
            sampled_target_path = actual_target_path
        # print(future_positions[best_index], sampled_target_path, actual_target_path[0], actual_target_path[-1])
        # print(action_list[best_index])
        return action_list[best_index], future_positions[best_index]

    def check_collision(self,start,end):
        '''
        return: the obstacle value distance in searched direction
        return (0, -1) when no obstacle is detected.
        '''
        start = (np.array(start)/self.map_resolution).astype(int)
        end = (np.array(end)/self.map_resolution).astype(int)
        # start = ((np.array(location) - np.array(self.map_origin)) /
        #             self.map_resolution).astype(int)
        # direction = np.array(direction)
        # end = start+(length*direction /
        #              (self.map_resolution*np.linalg.norm(direction))).astype(int)
        # print(start, end)
        value,distance = bresenham_line_search(self.map_data,start,end)
        collision = False
        if distance != -1:
            collision = True
        return collision, value, distance * self.map_resolution
        
    
    # def search_ray_obstacle(self,location,direction,length=3):
    #     '''
    #     return: the obstacle value distance in searched direction
    #     return (0, -1) when no obstacle is detected.
    #     '''
    #     # location = (self.location[0], self.location[1])
    #     start = ((np.array(location) - np.array(self.map_origin)) /
    #                 self.map_resolution).astype(int)
    #     direction = np.array(direction)
    #     end = start+(length*direction /
    #                  (self.map_resolution*np.linalg.norm(direction))).astype(int)
    #     value,distance = bresenham_line_search(self.map_data,start,end)
    #     distance *= self.map_resolution
    #     return value, distance
        # if semantic_value == COLOR_GRIDMAP['flat']:
        #     distance = length
        # # print(semantic_value)
        # return (COLOR_VOICE[semantic_value],distance)

    def visualize(self):
        self.map_data_visualize = self.map_data.copy()
        # self.map_data_visualize = self.map_data_visualize.reshape(self.map_height,self.map_height)
