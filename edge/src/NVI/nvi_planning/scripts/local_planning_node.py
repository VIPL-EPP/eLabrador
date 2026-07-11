#!/usr/bin/env python3
import nvi_octomap
import numpy as np
import rospy
import json
from octomap_msgs.msg import Octomap
from nav_msgs.msg import OccupancyGrid,Odometry
from std_msgs.msg import Header, String
from sensor_msgs.msg import Image
from nvi_msgs.msg import GPSTarget, Object, ObjectArray, HeaderString, HeaderFloat32
from local_planning.local_planner import LocalPlanner
# from local_planning import octree2gridmap
from local_planning.map_transform import octree2localprmap,octree2localprmap_height
# from local_planning import octree2localprmap2
from local_planning.map_transform import octree2localsemanticmap, octree2localsemanticmap_complete
# from local_planning import octree2localpotentialmap
from local_planning.map_draw import median_filter,edge_filter
import time
import tf



class NVILlocalPlanner(LocalPlanner):
    def __init__(self):
        super().__init__()
        self.parameter_init()
        rospy.init_node('nvi_local_planner', anonymous=True)
        self.semantic_map_pub = rospy.Publisher(
            "/semanticmap_full", OccupancyGrid, queue_size=10)
        self.pr_map_pub = rospy.Publisher(
            "/prmap_full", OccupancyGrid, queue_size=10)
        self.semantic_imgmap_pub = rospy.Publisher("/semantic_imgmap",Image,queue_size=10)
        self.objects_pub = rospy.Publisher(
            "/local_planning/objects", ObjectArray, queue_size=10)
        self.belt_pub = rospy.Publisher(
            "/local_planning/belt", HeaderString, queue_size=10)
        self.voice_pub = rospy.Publisher("/voice/system", String, queue_size=10)
        self.local_target_pub = rospy.Publisher("local_planning/target",HeaderFloat32,queue_size=10)  

        self.system_sub = rospy.Subscriber("/management/command",String,self.system_callback,queue_size=10)
        if self.is_work:
            self.subscribe()        
         
        # self.planning_count = 0
        self.spin()
        # rospy.spin()

        
    def spin(self):
        self.planning_rate = rospy.Rate(0.5)
        while not rospy.is_shutdown():
            if not self.check_work_status():
                self.planning_rate.sleep()
                continue
            self.update_time_stamp()
            if self.check_path_search_status():
                # t0 = time.perf_counter()
                SEARCH_OK = self.path_search()

                self.visualize()
                # self.draw_obstacle(90)
                if SEARCH_OK:
                    self.target_path_stamp = time.perf_counter()
                    self.draw_target_path()
                self.draw_coordinate_origin()
                # self.draw_location()
                # self.draw_direction()
                # self.draw_target_direction()
                # self.map_data_visualize = self.map_data_height
                # self.map_data_visualize[self.map_data_visualize>70]=100
                # self.map_data_visualize[self.map_data_visualize<70]=-1
                # img_msg = self.get_msg_from_image(self.map_data)
                # self.img_pub.publish(img_msg)
                pr_map_msg = self.get_msg_from_map(Header(frame_id="world"))
                self.pr_map_pub.publish(pr_map_msg)
            self.planning_rate.sleep()

    def parameter_init(self):
        self.is_work = True
        self.last_vibration_idx = 0

    def subscribe(self):
        self.map_sub = rospy.Subscriber("/octomap_full",Octomap, self.map_callback,queue_size=1)
        self.map4semantic_sub = rospy.Subscriber("/octomap_full",Octomap, self.map4semantic_callback,queue_size=1)

        self.vio_sub =  rospy.Subscriber("/vins_estimator/odometry", Odometry,
                         self.vio_callback, queue_size=1)
        self.global_target_sub = rospy.Subscriber("/global_planning/target", GPSTarget, self.global_target_callback, queue_size=1)

    def unsubscribe(self):
        self.map_sub.unregister()
        self.map4semantic_sub.unregister()
        self.vio_sub.unregister()
        self.global_target_sub.unregister()

    def system_callback(self,msg):
        rospy.loginfo(rospy.get_caller_id()+" I heard %s", msg.data)
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

    def map_callback(self, msg):
        octomap_msg = nvi_octomap.OctomapMsg(msg.id, msg.resolution, msg.data)
        octree = nvi_octomap.ColorOctree(octomap_msg)
        if self.location is None:
            rospy.loginfo("Self location initializing...")
            return
        map_data_pr, map_resolution, map_origin = octree2localprmap(octree, self.location)
        map_data_pr, map_resolution, map_origin, height_map_data = octree2localprmap_height(octree, self.location)
        map_data_pr = median_filter(map_data_pr, 3)
        self.set_map(map_data_pr, map_resolution, map_origin)
        height_map_data = edge_filter(height_map_data,ksize=3)
        self.add_height_map(height_map_data)
        # max_height, min_height = np.max(map_data_height),np.min(map_data_height)
        # self.map_data_height = ((map_data_height - min_height)*101/(max_height-min_height)-1).astype(np.int8)
 
    def map4semantic_callback(self,msg):
        octomap_msg = nvi_octomap.OctomapMsg(msg.id, msg.resolution, msg.data)
        octree = nvi_octomap.ColorOctree(octomap_msg)
        if self.location is None:
            rospy.loginfo("Self location initializing...")
            return
        map_data_semantic, map_resolution, map_origin = octree2localsemanticmap(octree,self.location)
        map_data_semantic = median_filter(map_data_semantic,3)
        self.set_semantic_map(map_data_semantic,map_resolution,map_origin)
        semantic_map_msg = self.get_msg_from_semantic_map(header=msg.header)
        self.semantic_map_pub.publish(semantic_map_msg)
        imgmap_semantic, map_resolution, map_origin = octree2localsemanticmap_complete(octree,self.location)
        semantic_imgmap_msg = self.get_msg_from_image(imgmap_semantic)
        self.semantic_imgmap_pub.publish(semantic_imgmap_msg)

    def vio_callback(self,msg):
        # print("VIO TIME",msg.header.stamp.to_time(),rospy.get_rostime().to_time())
        location = (msg.pose.pose.position.x, msg.pose.pose.position.y,msg.pose.pose.position.z)
        direction = self.quaternion2cartesian(msg.pose.pose.orientation)
        self.update_local_status((location,direction))
        location = (location[0],location[1])
        # path following
        if not self.check_path_follow_status():
            return
        # theta = self.pure_pursuit(location,direction)
        # theta = self.pure_pursuit_with_dis(location,direction)
        theta = self.pure_pursuit_with_obstacle_avoidance(location,direction)
        # print(theta,theta0)
        cmd =  self.theta2cmd(theta)
        if self.is_work:
            cmd = HeaderString(header=msg.header,data=cmd)
            self.belt_pub.publish(cmd)
            target  = HeaderFloat32(header=msg.header,data=theta)
            self.local_target_pub.publish(target)
            objects = self.get_objects(location,direction)
            objects_msg  = self.get_msg_from_objects(objects,header=msg.header)
            self.objects_pub.publish(objects_msg)
    
    def global_target_callback(self,msg):
        self.update_global_status((msg.direction.x,msg.direction.y))

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
    
    @staticmethod
    def quaternion2cartesian(quaternion):
        '''
        return the yaw in cartesian system. (x, y)
        '''
        # x right, y forward, z up.
        (p, r, y) = tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
        direction  = (-np.sin(y),np.cos(y))
        return direction

    def get_msg_from_map(self, header=Header()):
        msg = OccupancyGrid()
        msg.header = header
        msg.info.width = self.map_width
        msg.info.height = self.map_height
        msg.info.resolution = self.map_resolution
        msg.info.origin.position.x = self.map_origin[0]
        msg.info.origin.position.y = self.map_origin[1]
        msg.data = list(self.map_data_visualize.reshape(-1))
        return msg
    
    def get_msg_from_semantic_map(self, header=Header()):
        msg = OccupancyGrid()
        msg.header = header
        msg.info.width = self.map_width_semantic
        msg.info.height = self.map_height_semantic
        msg.info.resolution = self.map_resolution_semantic
        msg.info.origin.position.x = self.map_origin_semantic[0]
        msg.info.origin.position.y = self.map_origin_semantic[1]
        msg.data = list(self.map_data_smantic.reshape(-1))
        return msg
    
    def get_msg_from_objects(self,objects, header=Header()):
        msg = ObjectArray()
        msg.header = header
        for object in objects:
            msg.data.append(Object(semantic=object[0],direction=object[1],distance=object[2]))
        return msg
    
    def get_msg_from_image(self,image,header=Header()):
        msg = Image()
        msg.header = header
        msg.height = image.shape[0]
        msg.width = image.shape[1]
        if len(image.shape) == 3:
            msg.encoding = 'rgb8'
            msg.step = msg.width * 3
        elif len(image.shape) == 2:
            msg.encoding = 'mono8'
            msg.step = msg.width
        # msg.is_bigendian=True
        msg.data = image.tobytes()
        return msg


    def check_path_search_status(self):
        status_ok = True
        if self.location is None:
            status_ok = False
            rospy.loginfo("Self location initializing...")
        if self.target_direction is None:
            status_ok = False
            rospy.loginfo("Target direction initializing...")
        if self.map_data.size <=0:
            status_ok = False
            rospy.loginfo("Local map initializing...")
        return status_ok
    
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

if __name__ == "__main__":
    nvi_local_planner = NVILlocalPlanner()
