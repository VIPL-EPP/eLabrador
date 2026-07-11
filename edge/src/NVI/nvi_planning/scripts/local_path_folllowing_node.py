#!/usr/bin/env python3
import numpy as np
import rospy
import json
from nav_msgs.msg import Odometry, OccupancyGrid
from std_msgs.msg import String
from nvi_msgs.msg import TargetPath,HeaderString,HeaderFloat32
from local_planning.local_planner import LocalPlanner
import message_filters
import time
import tf
import math

class NVILlocalPathFollower(LocalPlanner):
    def __init__(self):
        super().__init__()
        self.parameter_init()
        rospy.init_node('nvi_local_path_follower', anonymous=True)
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

        self.spin()
        # rospy.spin()

        
    def spin(self):
        self.path_following_rate = rospy.Rate(1)
        while not rospy.is_shutdown():
            # if not self.check_work_status():
            #     self.planning_rate.sleep()
            #     continue
            if len(self.target_path) > 2:
                point1 = self.target_path[0]
                point2 = self.target_path[-1]
                point3 = self.target_path[-2]
                theta = math.atan(point1[1]-point2[1]/point1[0]-point2[0])
                theta2 = math.atan(point1[1]-point3[1]/point1[0]-point3[0])
                print(theta/math.pi*180, theta2/math.pi*180)
                if np.abs(theta/math.pi*180)>80:
                    print(np.abs(theta/math.pi*180))
                    self.turning_pub.publish('1')
                else:
                    self.turning_pub.publish('0')
            self.update_time_stamp(MAP_LIFE=10,PATH_LIFE=10)
            self.path_following_rate.sleep()

    def parameter_init(self):
        self.is_work = True
        self.last_vibration_idx = 0
        self.map_resolution = 0.2
        # self.path_search_log_once_flag = False
        self.is_log = {'searching':False,'follwoing':False}

    def subscribe(self):
        self.vio_sub =  rospy.Subscriber("/vins_estimator/odometry", Odometry, self.vio_callback, queue_size=1)
        # self.target_path_sub = rospy.Subscriber("/local_planning/target_path",TargetPath,self.target_path_callback,queue_size=1)
        # self.cost_map_sub = rospy.Subscriber("/local_planning/cost_map", OccupancyGrid,self.cost_map_callback,queue_size=1)
        self.target_path_filter_sub = message_filters.Subscriber("/local_planning/target_path", TargetPath)
        self.cost_map_filter_sub = message_filters.Subscriber("/local_planning/cost_map", OccupancyGrid)
        self.sync_path_map = message_filters.ApproximateTimeSynchronizer([self.target_path_filter_sub,self.cost_map_filter_sub], 10,0.1)
        self.sync_path_map.registerCallback(self.sync_path_map_callback)

    def unsubscribe(self):
        # self.target_path_sub.unregister()
        # self.cost_map_sub.unregister()
        self.target_path_filter_sub.unregister()
        self.cost_map_filter_sub.unregister()
        self.vio_sub.unregister()

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
        location = (msg.pose.pose.position.x, msg.pose.pose.position.y)
        direction = self.quaternion2cartesian(msg.pose.pose.orientation)
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
        theta = self.pure_pursuit_with_dis(location,direction)
        # theta = self.pure_pursuit_with_obstacle_avoidance(location,direction)
        # print(theta,theta0)
        cmd =  self.theta2cmd(theta)
        if self.is_work:
            cmd = HeaderString(header=msg.header,data=cmd)
            self.belt_pub.publish(cmd)
            target  = HeaderFloat32(header=msg.header,data=theta)
            self.local_target_pub.publish(target)
            self.angle_pub.publish(target)

    def theta2cmd(self,theta):
        vibration_idx =0
        theta_abs = abs(theta)
        if theta_abs> 90:
            # Push-pull complementary
            if self.last_vibration_idx <=2:
                vibration_idx =2
            else:
                vibration_idx = 4
        elif theta_abs > 40:
            vibration_idx = 2 if theta < 0 else  4
        # elif theta_abs > 25:
        #     vibration_idx = 1 if theta < 0 else  3
        self.last_vibration_idx = vibration_idx
        cmd = '0'+str(vibration_idx)+'1'
        return cmd
    
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
