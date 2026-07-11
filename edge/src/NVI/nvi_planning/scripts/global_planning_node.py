#!/usr/bin/env python3
import rospy
import tf
import numpy as np
import message_filters
from std_msgs.msg import String,Header,Float32MultiArray
import json
from nvi_msgs.msg import GPSTarget, Destination, HeaderFloat32
from nav_msgs.msg import Odometry,Path
from sensor_msgs.msg import NavSatFix,Imu
from geometry_msgs.msg import PoseStamped,Pose,Point
from global_planning.global_planner import GlobalPlanner
from global_planning.map_api import location2GPS
from global_planning.gps_transform import wgs842gcj02
from global_planning.gnss_compute import get_p2pdistance,get_p2ldistance,get_p2pazimuth,get_p2pgeodesic
from collections import deque
import copy
from global_planning.filter import KalmanFilterLLA
from nvi_msgs.msg import HeaderString

class NVIGlobalPlanner(GlobalPlanner):
    def __init__(self, start_location='', end_location=''):
        preset_way = None

        # Set the default start and end coordinates here.
        start_point = (40.05955,116.17297)
        end_point = (40.06257,116.18100)

        super().__init__(start_point, end_point, preset_way=preset_way)
        self.parameter_init()
        rospy.init_node('nvi_global_planner', anonymous=True)
        # self.global_cmd_pub = rospy.Publisher("/global_planning/voice", String, queue_size=10)
        self.voice_cmd_pub = rospy.Publisher("/voice/system", String, queue_size=10)
        self.global_status_pub = rospy.Publisher("/global_planning/status", String, queue_size=10)
        self.global_target_pub = rospy.Publisher("/global_planning/target", GPSTarget, queue_size=300)
        self.global_roads_pub = rospy.Publisher("/global_planning/roads", String, queue_size=1,latch=True)
        self.publish_global_roads()

        # Publish belt control commands through the existing Bluetooth bridge.
        self.belt_pub = rospy.Publisher("/local_planning/belt", HeaderString, queue_size=1)         
        
        if self.path_visulize:
            self.gloabl_path_pub = rospy.Publisher("/global_planning/path",Path,queue_size=10)
            self.gloabl_transformed_path_pub = rospy.Publisher("/global_planning/path/transformed",Path,queue_size=10)
            self.amap_path_pub = rospy.Publisher("/global_planning/amap_path",Path,queue_size=10)
            self.amap_transformed_path_pub = rospy.Publisher("/global_planning/amap_path/transformed",Path,queue_size=10)
            self.amap_path_pub.publish(self.amap_path_msg)
        self.subscribe()
        self.GPS2VIO = None
        rospy.spin()
    
    def parameter_init(self):
        self.DELTA_TIME = rospy.get_param("/global_planning/delta_time", default=5)
        self.TURN_DIS = rospy.get_param("/global_planning/turn_dis", default=20)
        self.RESET_DIS = rospy.get_param("/global_planning/reset_dis", default=25)
        self.POINT_BUFFER_SIZE = rospy.get_param("/global_planning/point_bufeer_size", default=100)
        self.path_visulize = rospy.get_param("/global_planning/path_visulize", default=False)
        self.MAX_PATH_LENGTH = 1000
        self.path_msg = Path()
        self.lla_seq = -1
        self.target_azimuth = None
        self.kf_lla = KalmanFilterLLA()
        self.is_arrived_buffer_var = False
        self.DESTINATION_PROTECTED_DIS = 15
        
        # Rotation-initialization state.
        self.is_rotation_initialized = False          # Whether the initial heading alignment is complete.
        self.consecutive_normal_angle_count = 0     # Number of consecutive frames with acceptable heading error.
    
    def subscribe(self):
        self.lla_sub = rospy.Subscriber("/ublox_driver/receiver_lla", NavSatFix, self.lla_callback,queue_size=1)
        self.destination_sub = rospy.Subscriber("/global_planning/destination",Destination,self.destination_callback)
        self.reset_sub = rospy.Subscriber("/global_planning/reset",String,self.reset_callback,queue_size=10)
        self.vio_filter_sub = message_filters.Subscriber("/vins_estimator/odometry", Odometry)
        self.mobile_orientation_filter_sub = message_filters.Subscriber("/mobile/orientation", HeaderFloat32)

        self.calibration_sub = rospy.Subscriber("/gps_vio_calib", Float32MultiArray, self.calibration_callback, queue_size=1)
        self.sync_vio_imu = message_filters.ApproximateTimeSynchronizer(
            [self.vio_filter_sub, self.mobile_orientation_filter_sub], 256, 0.01
        )
        # self.sync_vio_imu.registerCallback(self.sync_vio_imu_callback)
        self.sync_vio_imu.registerCallback(self.sync_vio_imu_with_init_callback)
        
        
    def unsubscribe(self):
        self.lla_sub.unregister()
        self.destination_sub.unregister()
        self.reset_sub.unregister()
        self.calibration_sub.unregister()

    def publish_global_roads(self):
        """
        Publish the raw self.roads object for data collection.
        Downstream parsing / coordinate transforms should be done in offline preprocessing.
        """
        if not hasattr(self, "global_roads_pub"):
            return

        # self.roads is usually a list[dict]. Make it JSON-serializable.
        # If it contains numpy types, convert them.
        def _to_jsonable(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.ndarray,)):
                return obj.tolist()
            return obj

        payload = {
            "coord_system": "gcj02_or_wgs84_latlon",  # you can later set this correctly
            "start_point": getattr(self, "start_point", None),
            "end_point": getattr(self, "end_point", None),
            "roads": getattr(self, "roads", None),
            "stamp": rospy.Time.now().to_sec(),
        }

        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False, default=_to_jsonable)
        self.global_roads_pub.publish(msg)

    def set_planner(self, start_point, end_point, preset_way=None):
        super().set_planner(start_point, end_point, preset_way=preset_way)
        self.amap_path_msg = Path()
        self.amap_path_msg.header = Header(frame_id="world")
        init_point = getattr(self, "init_point", start_point)
        cnt=0
        for road in self.roads:
            for point in road['polyline']:
                cnt += 1
                distance, azimuth=get_p2pgeodesic(init_point, point)
                azimuth = - np.deg2rad(azimuth)
                pose = Pose(position=(Point(distance*np.cos(azimuth),distance*np.sin(azimuth),0)))
                self.amap_path_msg.poses.append(PoseStamped(header=Header(seq=cnt,frame_id="world"),pose=pose))
        if getattr(self, 'path_visulize', False):
            self.amap_path_pub.publish(self.amap_path_msg)
        self.publish_global_roads()

    def calibration_callback(self, msg):
        R = np.array(msg.data[:4]).reshape(2,2)
        T = np.array(msg.data[4:])
        self.GPS2VIO = (R, T)

    def lla_callback(self, msg):
        if abs(msg.header.seq - self.lla_seq) > 100:
            self.path_msg.poses.clear()
            rospy.logwarn("lla message discontinue, reset the global planner.")
        self.lla_seq = msg.header.seq
        # gcj_loc = wgs842gcj02(msg.latitude, msg.longitude)
        gcj_loc = {
            'lat': msg.latitude,
            'lon': msg.longitude
        }
        now_point = (gcj_loc['lat'],gcj_loc['lon'])

        
        # now_point = self.kf_lla.update(now_point, msg.header.stamp.to_sec())
        if not self.is_set:
            self.set_planner(now_point,self.end_point)
            return
        self.update(now_point)
        cmd = self.get_audio_feedback()
        if cmd is not None:
            # print(cmd)
            self.voice_cmd_pub.publish(cmd)
        is_arrived, distance2end = self.is_arrived(now_point)
        # arrived proectection
        if is_arrived or (self.is_arrived_buffer_var and distance2end < self.DESTINATION_PROTECTED_DIS):
            self.global_status_pub.publish('arrived')
            self.is_arrived_buffer_var = True
        elif self.is_turn:
            self.global_status_pub.publish('turning')
        else:
            self.global_status_pub.publish('line following')
        if self.path_visulize:
            self.path_msg.header = Header(frame_id="world",stamp=msg.header.stamp)
            pose = Pose(position=(Point(self.path[-1][0],self.path[-1][1],0)))
            self.path_msg.poses.append(PoseStamped(header=Header(seq=len(self.path),frame_id="world",stamp=msg.header.stamp),pose=pose))
            if len(self.path_msg.poses) > self.MAX_PATH_LENGTH:
                self.path_msg.poses = self.path_msg.poses[-self.MAX_PATH_LENGTH:]
            self.gloabl_path_pub.publish(self.path_msg)
        if self.status >= 0:
            self.target_azimuth = self.get_target_azimuth(now_point)
            RT = copy.deepcopy(self.GPS2VIO)
            if RT is  None:
                rospy.logwarn_throttle(5.0, "GPS-to-VIO calibration is not available yet.")
                return
            else:
                rospy.loginfo_once('Global-Local calibration is done.')
            status, sub_status = self.status, self.sub_status
            azimuth = self.target_azimuth
            azimuth = - np.deg2rad(azimuth)
            point = np.array([np.cos(azimuth),np.sin(azimuth)])
            transformed_point = np.matmul(RT[0],point) #+ RT[1] # under vio coordinate
            # distance = self.roads[status]['polylength'][sub_status]
            distance = 0
            target_msg = self.get_gps_target_msg(transformed_point,distance,status=1,header=msg.header)
            self.global_target_pub.publish(target_msg)
            if self.path_visulize:
                transformed_path_msg =  self.get_transfromed_path_msg(self.path_msg,RT[0],RT[1])
                self.gloabl_transformed_path_pub.publish(transformed_path_msg)

                transformed_path_msg =  self.get_transfromed_path_msg(self.amap_path_msg,RT[0],RT[1])
                self.amap_transformed_path_pub.publish(transformed_path_msg)

    def destination_callback(self, msg):
        try:
            if msg.name != '': 
                end_point = location2GPS(msg.data)
            else:
                end_point = (msg.latitude, msg.longitude)
                start_point = (msg.start_latitude, msg.start_longitude)
            if start_point[0] == -1:
                start_point = self.start_point
            rospy.loginfo(f"Reset planner destination to {end_point}.")
            self.set_planner(start_point, end_point)
            rospy.loginfo('Set planner from '+str(start_point)+' to '+str(end_point)+'.')
        except:
            rospy.loginfo("Invalid destination location.")
    
    def reset_callback(self, msg):
        if msg.data == 'audio_feedback':
            self.reset_audio_feedback()

    def calculate_turn_angle(self,azimuth, global_orientation_direction):
        """
        Compute the signed rotation needed to align the current heading with
        the target heading.

        Positive values indicate clockwise/right turns, while negative values
        indicate counter-clockwise/left turns.
        """
        # Normalize the target heading to the [0, 360) range.
        target_angle = azimuth % 360
        
        # The current heading is already expressed in the same range.
        current_angle = global_orientation_direction % 360
        
        # Compute the clockwise delta.
        total_turn = (target_angle - current_angle) % 360
        
        # Convert it to the shortest signed rotation in [-180, 180].
        if total_turn > 180:
            turn_angle = total_turn - 360
        else:
            turn_angle = total_turn
        
        return turn_angle

    def sync_vio_imu_callback(self, vio_msg, mobile_orientation_msg):
        rospy.logdebug("Received synchronized VIO and mobile orientation messages.")
        if self.GPS2VIO is not None:
            rospy.logdebug("GPS2VIO is already calibrated; skipping sync_vio_imu_callback.")
            # return
        global_orientation_direction = float(mobile_orientation_msg.data)
        self.update_direction(global_orientation_direction)
        vio_orientation = self.quaternion2cartesian(vio_msg.pose.pose.orientation)
        status = self.status
        sub_status = self.sub_status
        rospy.logdebug(f"Current planner status: {status}")
        if status >= 0 and self.target_azimuth is not None:
            azimuth = self.target_azimuth

            # clock direction, 0 is the tarhet direction
            # azimuth = self.roads[status]['polyazimuth'][sub_status]
            # print("!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # print(azimuth)
            dazimuth = self.calculate_turn_angle(azimuth, global_orientation_direction)
            taret_direction = self.point2d_rotation(vio_orientation,np.deg2rad(dazimuth))
            # distance = self.roads[status]['polylength'][sub_status]
            target_msg = self.get_gps_target_msg(taret_direction,0,status=0,header=vio_msg.header)
            self.global_target_pub.publish(target_msg)

    def sync_vio_imu_with_init_callback(self, vio_msg, mobile_orientation_msg):
            rospy.logdebug("Received synchronized VIO and mobile orientation messages.")
            if self.GPS2VIO is not None:
                rospy.logdebug("GPS2VIO is already calibrated; skipping sync_vio_imu_callback.")
                return
                
            global_orientation_direction = float(mobile_orientation_msg.data)
            # print(f"-------------------++++++++++++{global_orientation_direction}++++++++++++-----------------")
            self.update_direction(global_orientation_direction)
            vio_orientation = self.quaternion2cartesian(vio_msg.pose.pose.orientation)
            status = self.status
            # sub_status = self.sub_status
            
            if status >= 0 and self.target_azimuth is not None:
                azimuth = self.target_azimuth
                # Compute the signed turn needed from the current heading to the target heading.
                dazimuth = self.calculate_turn_angle(azimuth, global_orientation_direction)
                
                # Belt guidance during the heading-initialization stage.
                # Before initialization completes, publish belt commands only and skip target_msg.
                if not getattr(self, 'is_rotation_initialized', False):
                    try:
                        # Create the belt command.
                        belt_cmd = HeaderString()
                        belt_cmd.header.stamp = rospy.Time.now()
                        
                        # Choose the belt command based on the heading error.
                        if dazimuth > 30:
                            # Heading error is larger than 30 deg: trigger the left vibration pattern 021.
                            belt_cmd.data = "021"
                            rospy.loginfo(f"[Belt] Heading drifts left by {dazimuth:.1f} deg -> command 021")
                            # Reset the consecutive-success counter while initialization is still active.
                            if not getattr(self, 'is_rotation_initialized', False):
                                self.consecutive_normal_angle_count = 0
                                
                        elif dazimuth < -30:
                            # Heading error is smaller than -30 deg: trigger the right vibration pattern 041.
                            belt_cmd.data = "041"
                            rospy.loginfo(f"[Belt] Heading drifts right by {dazimuth:.1f} deg -> command 041")
                            # Reset the consecutive-success counter while initialization is still active.
                            if not getattr(self, 'is_rotation_initialized', False):
                                self.consecutive_normal_angle_count = 0
                                
                        else:
                            # Heading is within range: stop vibration with command 000.
                            belt_cmd.data = "000"
                            
                            # Count consecutive in-range frames until initialization finishes.
                            if not getattr(self, 'is_rotation_initialized', False):
                                self.consecutive_normal_angle_count += 1
                                rospy.loginfo(f"[Init] Heading within range. Consecutive good frames: {self.consecutive_normal_angle_count}/3")
                                
                                # Unlock normal navigation after three consecutive valid frames.
                                if self.consecutive_normal_angle_count >= 3:
                                    self.is_rotation_initialized = True
                                    rospy.loginfo("Rotation initialization completed. Normal navigation enabled.")
                                    # Optional voice prompt; keep this commented unless voice_cmd_pub is required here.
                                    # self.voice_cmd_pub.publish("Heading alignment complete. Please walk forward.")

                        # Publish the belt command.
                        self.belt_pub.publish(belt_cmd)
                        
                    except Exception as e:
                        rospy.logwarn(f"Failed to publish belt command: {str(e)}")

                    return  

                # Publish target_msg after initialization is complete.
                # print(f"-------vio_orientation: {vio_orientation}, target_azimuth:{self.target_azimuth}, dazimuth: {dazimuth}-------")
                taret_direction = self.point2d_rotation(vio_orientation, np.deg2rad(dazimuth))
                # distance = self.roads[status]['polylength'][sub_status]
                target_msg = self.get_gps_target_msg(taret_direction, 0, status=0, header=vio_msg.header)
                self.global_target_pub.publish(target_msg)

  
    @staticmethod
    def quaternion2cartesian(quaternion):
        '''
        return the yaw in cartesian system. (x, y)
        '''
        # x right, y forward, z up.
        (p, r, y) = tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
        direction  = (np.sin(y),np.cos(y))
        return direction
    
    @staticmethod
    def quaternion2euler(quaternion):
        '''
        return the eule angles of orientation quaternion.
        '''
        return tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
    
    @staticmethod
    def vector2angle(vector1,vector2):
        '''
        return the angle of v2 relative to v2. clock angle (-90 0 90) in degree . 
        '''
        vector1,vector2  = np.array(vector1),np.array(vector2)
        vector1 /= np.linalg.norm(vector1)
        vector2 /= np.linalg.norm(vector2)
        theta = np.arctan2(np.cross(vector1,vector2,),np.dot(vector1,vector2))
        return np.degrees(theta)

    @staticmethod
    def point2d_rotation(point,theta):
        '''
        point: (x, y); theta: rad
        '''
        x, y = point
        # theta is already expressed in radians here.
        # theta = np.radians(theta)
        x_ = x * np.cos(theta) + y * np.sin(theta)   
        y_ = - x*np.sin(theta) + y * np.cos(theta)  
        # print(f"theta: {theta}, cos: {np.cos(theta)}, rotated_point: {(x_, y_)}") 
        return (-x_, y_)  # Keep the axis ordering aligned with the latitude/longitude convention.

    def get_transfromed_path_msg(self,path_msg,R,T):
        assert len(T)==2, "The transformed points are 2 dimensions."
        transfromed_path_msg = copy.deepcopy(path_msg)
        for pose_stamped  in transfromed_path_msg.poses:
            point = np.array([pose_stamped.pose.position.x,pose_stamped.pose.position.y])
            transformed_point = np.matmul(R,point)+T
            pose_stamped.pose.position.x,pose_stamped.pose.position.y = transformed_point[0],transformed_point[1]
        return transfromed_path_msg
    
    def get_gps_target_msg(self,direction, distance, status=0,header=Header()):
        '''
        status: 0-magnetometer-vio-direction, 1-gps-vio-direction
        '''
        target_msg   = GPSTarget()
        target_msg.direction.x, target_msg.direction.y =  direction
        target_msg.header.stamp = header.stamp
        target_msg.distance = distance
        target_msg.status = status
        return target_msg
            

if __name__ == '__main__':
    nvi_global_planner = NVIGlobalPlanner()

        
        

