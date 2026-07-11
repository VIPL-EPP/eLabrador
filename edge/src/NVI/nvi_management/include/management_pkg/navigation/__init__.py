import string, zhon, re, dimsim
import rospy, roslib.packages, roslaunch
from nvi_msgs.msg import Destination, HeaderString
from std_msgs.msg import Header, String
import json
import os
from sensor_msgs.msg import NavSatFix,Imu
import threading
from management_pkg.utils import remove_punctuation, calculate_text_distance, CONFIG_DIR
from global_planning.gps_transform import wgs842gcj02



class RouteConfig:
    def __init__(self,name='',end_point=(0,0),landmark='',destination=''):
        self.name = name
        self.end_point = end_point
        self.landmark = landmark
        self.destination = destination
    
    def __repr__(self):
        return '({},{},{},{})'.format(self.name,self.end_point,self.landmark,self.destination)
        

class NavigationController:
    def __init__(self, key_msg_table):
        self.destination_pub = rospy.Publisher("/global_planning/destination",Destination,queue_size=1, latch=True)
        self.landmark_pub = rospy.Publisher("/servo/landmark", HeaderString, queue_size=1, latch=True)
        self.route_config_path = rospy.get_param("/nvi_management/route_config_path", default=CONFIG_DIR+"/route_config.json")
        self.parse_config_file(self.route_config_path)
        self.key_msg_table = key_msg_table
        # self.navigation_launch = None
    
    def parse_config_file(self,file_path):
        self.routes = {}
        with open(file_path, encoding='utf-8') as _file:
            json_file = json.load(_file)
            for route in json_file:
                end_point = (route['end']['latitude'],route['end']['longitude'])
                self.routes[route['name']] = RouteConfig(route['name'],end_point,route['landmark'],route['destination'])
    
    def check_set_destination(self, text):
        text = remove_punctuation(text)
        if calculate_text_distance(text[:3], "带我去") < 1:
            return True
        return False

    def try_to_find_lla(self, key_msg_table):
        return None
        msg_list = key_msg_table.key_msg_list
        for idx, msg in enumerate(msg_list):
            if "/ublox_driver/receiver_lla" == msg.msg:
                lla_ros = key_msg_table.last_check[idx][1]
                # gcj_loc = wgs842gcj02(lla_ros.latitude, lla_ros.longitude)
                gcj_loc = {
                    'lat': lla_ros.latitude,
                    'lon': lla_ros.longitude
                }
                now_point = (gcj_loc['lat'], gcj_loc['lon'])
                return now_point
        return None

    def set_destination(self, text):
        text = remove_punctuation(text)
        # import pdb; pdb.set_trace()
        destination = text[3:]
        for route in self.routes.values():
            if calculate_text_distance(destination, route.destination) < 1:
                start_point = self.try_to_find_lla(self.key_msg_table)
                if start_point is None:
                    start_point = (-1, -1)
                self.set_route(start_point, route.name)
                return True, "目的地设置为{}".format(route.destination)
        return False, "无法找到目的地"
    
    # TODO: launch navigation nodes in management node
    # def launch_navigation_node(self):
    #     if self.navigation_launch is None:
    #         bringup_dir = roslib.packages.get_pkg_dir("nvi_bringup")
    #         launch_file = os.path.join(bringup_dir, "launch", "nvi_navigation.launch")
    #         uuid = roslaunch.rlutil.get_or_generate_uuid(None, False)
    #         roslaunch.configure_logging(uuid)
    #         self.navigation_launch = roslaunch.parent.ROSLaunchParent(uuid, [launch_file])
    #         self.navigation_launch.start()
            

    #         # wait for start up
    #         rospy.sleep(1)
            
    #         def status_callback(msg):
    #             if msg.data == "arrived":
    #                 self.navigation_launch.shutdown()
    #                 self.status_sub.unregister()
    #                 del self.status_sub

    #         self.status_sub = rospy.Subscriber("/nvi_navigation/status", String, status_callback, queue_size=10)

    def set_route(self, start_point, route_name):
        header = Header(stamp = rospy.Time.now())
        route = self.routes[route_name]
        end_point = route.end_point
        landmark = route.landmark
        # TODO: launch navigation nodes in management node
        # if self.navigation_launch is None:
        #     self.launch_navigation_node()
        destination = Destination(header=header,name='',latitude=end_point[0],longitude=end_point[1], start_latitude=start_point[0], start_longitude=start_point[1])
        landmark = HeaderString(header=header,data=landmark)
        self.destination_pub.publish(destination)
        self.landmark_pub.publish(landmark)
        rospy.loginfo('Publish destination: '+route_name)
