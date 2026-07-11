import rospy
from nvi_msgs.msg import Destination, HeaderString
from std_msgs.msg import Header
import json
import os
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PAR_DIR = os.path.dirname(CURRENT_DIR)


class RouteConfig:
    def __init__(self,name='',start_point=(0,0),end_point=(0,0),landmark='',destination=''):
        self.name = name
        self.start_point = start_point
        self.end_point = end_point
        self.landmark = landmark
        self.destination = destination
    
    def __repr__(self):
        return '({},{},{},{},{})'.format(self.name,self.start_point,self.end_point,self.landmark,self.destination)
        

class NVISystemConfig:
    def __init__(self):
        rospy.init_node('nvi_system_config', anonymous=True) 
        self.destination_pub = rospy.Publisher("/global_planning/destination",Destination,queue_size=1, latch=True)
        self.landmark_pub = rospy.Publisher("/servo/landmark", HeaderString, queue_size=1, latch=True)  
        self.route_config_path = rospy.get_param("/nvi_system_config/route_config_path", default=PAR_DIR+"/config/route_config.json")
        self.route_name = rospy.get_param("/nvi_system_config/route_name", default="")
        self.parse_config_file(self.route_config_path)
        self.publish()
        rospy.spin()
    
    def parse_config_file(self,file_path):
        self.routes = {}
        with open(file_path, encoding='utf-8') as _file:
            json_file = json.load(_file)
            for route in json_file:
                start_point = (route['start']['latitude'],route['start']['longitude'])
                end_point = (route['end']['latitude'],route['end']['longitude'])
                self.routes[route['name']] = RouteConfig(route['name'],start_point,end_point,route['landmark'],route['destination'])
        
    def publish(self):
        if self.route_name not in self.routes:
            rospy.logwarn_once('The route name '+self.route_name+' is not included in conifg file '+self.route_config_path)
            return
        header = Header(stamp = rospy.Time.now())
        route = self.routes[self.route_name]
        destination = Destination(header=header,name='',latitude=route.end_point[0],longitude=route.end_point[1],start_latitude=route.start_point[0],start_longitude=route.start_point[1])
        landmark = HeaderString(header=header,data=route.landmark)
        self.destination_pub.publish(destination)
        self.landmark_pub.publish(landmark)
        rospy.loginfo('Publish destination: '+self.route_name)


        
if __name__ == '__main__':
    nvi_system_config = NVISystemConfig()
