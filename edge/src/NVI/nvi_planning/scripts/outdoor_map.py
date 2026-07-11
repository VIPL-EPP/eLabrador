#!/usr/bin/env python3
import numpy as np
import rospy
import json
from nvi_msgs.msg import GPSTarget, TargetWaypoint, TargetPath, Object, ObjectArray
from std_msgs.msg import String, Header
from nvi_msgs.msg import TargetPath,HeaderString,HeaderFloat32
from nav_msgs.msg import OccupancyGrid, Odometry
from local_planning.local_planner import LocalPlanner
import message_filters
import time
import tf
import math
import cv2
import jsonlines

class NVILlocalPathFollower(LocalPlanner):
    def __init__(self):
        super().__init__()
        self.parameter_init()
        rospy.init_node('nvi_local_path_follower', anonymous=True)
        self.pr_map_pub = rospy.Publisher(
            "/prmap_full", OccupancyGrid, queue_size=1)
        self.belt_pub = rospy.Publisher(
            "/local_planning/belt", HeaderString, queue_size=10)
        self.voice_pub = rospy.Publisher("/voice/system", String, queue_size=10)  
        self.local_target_pub = rospy.Publisher("local_planning/target",HeaderFloat32,queue_size=10)  
        self.system_sub = rospy.Subscriber("/management/command",String,self.system_callback,queue_size=10)
        self.global_status_sub = rospy.Subscriber("/global_planning/status",String,self.global_status_callback,queue_size=10)
        self.angle_pub = rospy.Publisher("/local_planning/interaction", HeaderFloat32, queue_size=10)
        self.turning_pub = rospy.Publisher("/local_planning/turning/interaction", String, queue_size=10)
        if self.is_work:
            self.subscribe()        
        self.first_vio = False
        self.is_correcting = False
        self.time_list = []
        self.action_time = 0.5
        self.success = False
        self.origin_position = None
        self.origin_orientation = None
        self.position = None
        self.direction = None
        self.imagine_step = 5
        self.pose_list = []
        self.action_list = [[1, 0, 0] for _ in range(10)]
        self.predicted_poses = None
        self.spin()
        # rospy.spin()

        
    def spin(self):
        self.path_following_rate = rospy.Rate(1)
        while not rospy.is_shutdown():
            print('--------------------------------------------------')
            self.visualize()
            if self.location is not None and self.direction is not None:
                self.draw_location(self.location, self.direction)
                if self.predicted_poses is not None:
                    for item in self.predicted_poses:
                        self.draw_path(item)
            pr_map_msg = self.get_msg_from_map(Header(frame_id="world"))
            self.pr_map_pub.publish(pr_map_msg)
            self.update_time_stamp(MAP_LIFE=10,PATH_LIFE=10)
            self.path_following_rate.sleep()
        # with jsonlines.open('coordinate.jsonl', mode='a') as writer:
        #     for location in self.location_list:
        #         temp = {'x': location[0], 'y': location[1]}
        #         writer.write(temp)

    def parameter_init(self):
        self.is_work = True
        self.last_vibration_idx = 0
        self.map_resolution = 0.2
        # self.path_search_log_once_flag = False
        self.is_log = {'searching':False,'follwoing':False}

    def subscribe(self):
        self.action_sub = rospy.Subscriber('/belt/actual_vibration', HeaderString, self.action_callback, queue_size=1)
        self.vio_sub =  rospy.Subscriber("/vins_estimator/odometry", Odometry, self.vio_callback, queue_size=1)
        self.target_path_sub = rospy.Subscriber("/local_planning/target_path",TargetPath,self.target_path_callback,queue_size=1)
        # self.cost_map_sub = rospy.Subscriber("/local_planning/cost_map", OccupancyGrid,self.cost_map_callback,queue_size=1)
        # self.target_path_filter_sub = message_filters.Subscriber("/local_planning/target_path", TargetPath)
        # self.cost_map_filter_sub = message_filters.Subscriber("/local_planning/cost_map", OccupancyGrid)
        # self.sync_path_map = message_filters.ApproximateTimeSynchronizer([self.target_path_filter_sub,self.cost_map_filter_sub], 10,0.1)
        # self.sync_path_map.registerCallback(self.sync_path_map_callback)

    def unsubscribe(self):
        # self.target_path_sub.unregister()
        # self.cost_map_sub.unregister()
        self.target_path_filter_sub.unregister()
        self.cost_map_filter_sub.unregister()
        self.vio_sub.unregister()

    def update_location(self):
        
        point1 = [self.location_list[-31][0]-self.location_list[-1][0], self.location_list[-31][1]-self.location_list[-1][1]]
        point2 = [self.location_list[-21][0]-self.location_list[-1][0], self.location_list[-21][1]-self.location_list[-1][1]]
        point3 = [self.location_list[-11][0]-self.location_list[-1][0], self.location_list[-11][1]-self.location_list[-1][1]]
        print([point1, point2, point3])
        self.pursuit_with_prediction(self.location_list[-1], [point1, point2, point3])
        if self.distance(self.location_list[-1], self.terminal) <= 2:
            print('Successfully following')
            self.success = True
    
    

    def action_callback(self,msg):
        # print("ACTION TIME",msg.header.stamp.to_time(),rospy.get_rostime().to_time())
        data = msg.data
        if data == '000':
            self.action_list.append([1, 0, 0])
        elif data == '041':
            self.action_list.append([0, 0, 1])
        elif data == '021':
            self.action_list.append([0, 1, 0])

    def system_callback(self,msg):
        # rospy.loginfo(rospy.get_caller_id()+" I heard %s", msg.data)
        try:
            command = json.loads(msg.data)
            if command["to"] != "local_planning":
                return
            self.is_work = command["work"]
        except:
            rospy.logwarn("Invalid system message")
            return
        if self.is_work:
            self.subscribe()
            self.voice_pub.publish("局部导航已开启")
        else:
            self.unsubscribe()
            self.voice_pub.publish("局部导航已关闭")
    
    def global_status_callback(self,msg):
        if msg.data =='arrived' and self.is_work is True:
            self.is_work = False
            self.unsubscribe()
        if msg.data != 'arrived' and self.is_work is False:
            self.is_work = True
            self.subscribe()

    def target_path_callback(self,msg):
        target_path = []
        for waypoint in msg.data:
            target_path.append((waypoint.x,waypoint.y))
        self.target_path = target_path
    
    def cost_map_callback(self, msg):
        map_data = np.array(msg.data)
        map_data = map_data.reshape((msg.info.height,msg.info.width))
        self.set_map(map_data,(msg.info.origin.position.x,msg.info.origin.position.y))

    def sync_path_map_callback(self, path_msg, map_msg):
        # print("SYNC_PATH_MAP TIME",path_msg.header.stamp.to_time(),map_msg.header.stamp.to_time())
        target_path = []
        for waypoint in path_msg.data:
            target_path.append((waypoint.x,waypoint.y))
        self.target_path = target_path
        map_data = np.array(map_msg.data)
        map_data = map_data.reshape((map_msg.info.height,map_msg.info.width))
        self.set_map(map_data,map_msg.info.resolution, (map_msg.info.origin.position.x,map_msg.info.origin.position.y))
        self.target_path_stamp = time.perf_counter()
    
    def vio_callback(self,msg):
        # print("VIO TIME",msg.header.stamp.to_time(),rospy.get_rostime().to_time())
        start = time.time()
        selected_poses = []
        self.pose_list.append(msg)
        # Assume T is defined somewhere
        T = 10  # Example value for T
        # Select last T actions
        last_T_actions = self.action_list[-T:] if hasattr(self, 'action_list') else []
        # Extract T poses with the shortest time interval from the end of self.pose_list
        pose_indices = []
        current_time = rospy.get_rostime().to_time()
        pose_list = self.pose_list[-10*T:]
        # align timestamp
        for i, action in enumerate(last_T_actions):
            if i == len(last_T_actions) - 1:
                action_time = current_time
            else:
                action_time = current_time - (len(last_T_actions) - 1 - i)
            min_time_diff = float('inf')
            min_index = -1
            closest_pose = None
            for pose in reversed(pose_list):
                pose_time = pose.header.stamp.to_time()
                time_diff = abs(pose_time - action_time)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_pose = pose

            if closest_pose is not None:
                selected_poses.append(closest_pose)
                pose_list.remove(closest_pose)
        # print(selected_poses)
        positions = []
        poses = []
        for item in selected_poses:
            position = np.array([item.pose.pose.position.x, item.pose.pose.position.y, item.pose.pose.position.z])
            orientation = np.array([item.pose.pose.orientation.x, item.pose.pose.orientation.y, item.pose.pose.orientation.z, item.pose.pose.orientation.w])
            angular_velocity = np.array([item.twist.twist.angular.x, item.twist.twist.angular.y, item.twist.twist.angular.z])
            linear_velocity = np.array([item.twist.twist.linear.x, item.twist.twist.linear.y, item.twist.twist.linear.z])
            if len(poses) == 0:
                position_data = [0, 0, 0]
            else:
                prev_position = positions[-1]
                position_data = [position[i] - prev_position[i] for i in range(3)]
            # print(position_data)
            pose = np.concatenate([position_data, angular_velocity, orientation, linear_velocity])
            poses.append(pose)
            positions.append(position)
        poses = np.array(poses)
        # print([p[0:2] for p in poses])
        last_T_actions = np.array(last_T_actions)
        # path following
        if not self.check_path_follow_status():
            if not self.is_log['searching']:
                self.voice_pub.publish('停止停止正在为您重新规划路线')
                self.is_log['searching'] = True
                self.is_log['follwoing'] = False
            return
        if not self.is_log['follwoing']:
            self.is_log['follwoing'] = True
            self.is_log['searching'] = False
            self.voice_pub.publish('已重新规划路线请开始行走')
        # theta = self.pure_pursuit(location,direction)
        if self.first_vio is False:
            self.first_vio = True
            self.origin_position = (msg.pose.pose.position.x,msg.pose.pose.position.y)
            self.origin_orientation = self.quaternion2cartesian(msg.pose.pose.orientation)
        
        location = [msg.pose.pose.position.x, msg.pose.pose.position.y]
        self.location = location
        direction = self.quaternion2cartesian(msg.pose.pose.orientation)
        self.direction = direction
        # print(self.location)
        # print(self.direction)
        output = self.imagine(poses, last_T_actions, self.imagine_step)
        output = [tensor.detach().numpy() for tensor in output]
        output = np.stack(output, axis=0)
        # generate 10 numbers randomly between [0, 242]
        random_numbers = np.random.randint(0, 242, 242)
        # predicted_poses = []
        actual_locations_list = []
        # coordinate convert
        for number in random_numbers:
            predicted_pose = [output[i][0][number][0:2] for i in range(0, self.imagine_step)]
            actual_locations = [np.array(location)]
            for i in range(len(predicted_pose)):
                prev_location = actual_locations[-1]
                actual_location = prev_location + predicted_pose[i]
                actual_locations.append(actual_location)
            actual_locations_list.append(actual_locations[1:])

        top_k_path, top_k_action = self.select_path(actual_locations_list, self.target_path)
        # print(output[0].shape, len(output), top_k_action)
        self.predicted_poses = top_k_path
        end = time.time()
        # print(poses)
        # print(top_k_path[0])
        # print(end - start)
        # print(top_k_action[0])
        # print(actual_locations_list)

        # cmd =  self.theta2cmd_easy(theta)
        # if cmd is not None:
        #     cmd = HeaderString(header=msg.header,data=cmd)
        #     self.belt_pub.publish(cmd)
            

    def get_msg_from_target_path(self,header_=Header()):
        msg = TargetPath()
        msg.header = header_
        for target_waypoint in self.target_path:
            msg.data.append(TargetWaypoint(x=target_waypoint[0],y=target_waypoint[1]))
        return msg

    
    def get_msg_from_map(self, header_=Header()):
        msg = OccupancyGrid()
        msg.header = header_
        msg.info.width = self.map_width
        msg.info.height = self.map_height
        msg.info.resolution = self.map_resolution
        msg.info.origin.position.x = self.map_origin[0]
        msg.info.origin.position.y = self.map_origin[1]
        msg.data = list(self.map_data_visualize.reshape(-1))
        return msg
    
    def theta2cmd(self,theta):
        vibration_idx =0
        theta_abs = abs(theta)
        if theta_abs> 90:
            # Push-pull complementary
            if self.last_vibration_idx <=2:
                vibration_idx =2
            else:
                vibration_idx = 4
        elif theta_abs >30:
            vibration_idx = 2 if theta <0 else  4
        elif theta_abs >10:
            vibration_idx = 1 if theta <0 else  3
        self.last_vibration_idx = vibration_idx
        cmd = '0'+str(vibration_idx)+'1'
        return cmd
    
    def theta2cmd_easy(self,theta):
        theta_abs = abs(theta)
        if self.is_correcting:
            if theta_abs > 5:
                vibration_idx = 2 if theta < 0 else 4
                return '0'+str(vibration_idx)+'1'
            else:
                self.is_correcting = False
                return None
        else:
            if theta_abs > 30:
                self.is_correcting = True
            return None
    
    @staticmethod
    def quaternion2cartesian(quaternion):
        '''
        return the yaw in cartesian system. (x, y)
        '''
        # x right, y forward, z up.
        (p, r, y) = tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
        direction  = (-np.sin(y),np.cos(y))
        return direction
    
    def check_path_follow_status(self):
        status_ok = True
        if not self.target_path:
            status_ok = False
            rospy.loginfo("Targt path searching...")
        return status_ok
    
    def check_work_status(self):
        if not self.is_work:
           rospy.loginfo("Local planning is waiting...") 
           return False
        return True

    def update_time_stamp(self,MAP_LIFE=60,PATH_LIFE=30):
        time_now = time.perf_counter()
        if time_now - self.target_path_stamp > PATH_LIFE:
            self.target_path = []
            self.target_path_stamp = time_now
        if time_now - self.map_stamp > MAP_LIFE:
            self.target_path = []
            self.map_stamp = time_now
        

if __name__ == "__main__":
    nvi_local_path_follwer = NVILlocalPathFollower()

# apply prediction model to scenario in the wild
# check if the prediction model's prediction correct or not
# visualization
# convert the best action sequence to vibration