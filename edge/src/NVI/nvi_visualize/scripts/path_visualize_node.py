#!/usr/bin/env python
from std_msgs.msg import String
from nav_msgs.msg import Odometry,Path
from sensor_msgs.msg import NavSatFix,Imu
from geometry_msgs.msg import PoseStamped,Pose,Point
import rospy
from sensor_msgs.msg import Image, CompressedImage
import tf2_geometry_msgs
from geometry_msgs.msg import Point, PointStamped
import tf2_ros
from cv_bridge import CvBridge, CvBridgeError
import numpy as np
import time
import message_filters
import json
import roslib
from functools import partial
import pyproj

def ecef_to_enu(x, y, z, x_ref, y_ref, z_ref):
    # 差值
    dx = x - x_ref
    dy = y - y_ref
    dz = z - z_ref

    # 转换为ENU坐标
    lat_ref_rad = np.arctan2(z_ref, np.sqrt(x_ref**2 + y_ref**2))
    lon_ref_rad = np.arctan2(y_ref, x_ref)
    sin_lat = np.sin(lat_ref_rad)
    cos_lat = np.cos(lat_ref_rad)
    sin_lon = np.sin(lon_ref_rad)
    cos_lon = np.cos(lon_ref_rad)

    x_enu = -sin_lon*dx + cos_lon*dy
    y_enu = -sin_lat*cos_lon*dx - sin_lat*sin_lon*dy + cos_lat*dz
    z_enu = cos_lat*cos_lon*dx + cos_lat*sin_lon*dy + sin_lat*dz

    return x_enu, y_enu, z_enu


class PathVisualize:
    def __init__(self):
        rospy.init_node('nvi_path_visualize', anonymous=True)
        # import ipdb; ipdb.set_trace()
        print(rospy.get_param_names())
        self.gps_topics = rospy.get_param('/nvi_path_visualize/gps_topics').split(',')
        self.vio_topic = rospy.get_param('/nvi_path_visualize/vio_topic')
        self.vio_sub = rospy.Subscriber(self.vio_topic, Odometry, self.vio_callback)
        self.gps_subs = [rospy.Subscriber(topic, NavSatFix, partial(self.gps_callback, idx)) for idx, topic in enumerate(self.gps_topics)]
        self.gps_init_points = [None for _ in range(len(self.gps_topics))]
        self.vio_init_point = None
        self.vio_pub = rospy.Publisher('nvi_vio_path', Path, queue_size=10)
        self.gps_pubs = [rospy.Publisher(f'{self.gps_topics[idx]}_path', Path, queue_size=10) for idx in range(len(self.gps_topics))]
        # frame_id = 'map'
        self.vio_path = Path()
        self.vio_path.header.frame_id = 'map'
        self.gps_paths = [Path() for _ in range(len(self.gps_topics))]
        for path in self.gps_paths:
            path.header.frame_id = 'map'
        
        rospy.spin()

    def vio_callback(self, msg):
        if self.vio_init_point is None:
            self.vio_init_point = msg.pose.pose.position
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        pose.pose.position.x -= self.vio_init_point.x
        pose.pose.position.y -= self.vio_init_point.y
        pose.pose.position.z -= self.vio_init_point.z
        self.vio_path.poses.append(pose)
        self.vio_pub.publish(self.vio_path)
    
    def gps_callback(self, idx, msg):
        pose = PoseStamped()
        pose.header = msg.header
        # calculate enu from gps
        lat = msg.latitude
        lon = msg.longitude
        alt = msg.altitude

        if self.gps_init_points[idx] is None:
            self.gps_init_points[idx] = [lat, lon, alt]
        lat0, lon0, alt0 = self.gps_init_points[idx]
        ecef = pyproj.Proj(proj='geocent', ellps='WGS84', datum='WGS84')
        lla = pyproj.Proj(proj='latlong', ellps='WGS84', datum='WGS84')
        x, y, z = pyproj.transform(lla, ecef, lon, lat, alt)
        x0, y0, z0 = pyproj.transform(lla, ecef, lon0, lat0, alt0)
        x, y, z = ecef_to_enu(x, y, z, x0, y0, z0)

        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = z
        self.gps_paths[idx].poses.append(pose)
        self.gps_pubs[idx].publish(self.gps_paths[idx])
    
        


if __name__ == '__main__':
    nvi_ocr = PathVisualize()
