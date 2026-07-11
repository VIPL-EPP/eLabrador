import rospy
from std_msgs.msg import Header
from sensor_msgs.msg import NavSatFix
import copy
import time
import socket
import threading

class PhoneGPS:
    def __init__(self):
        rospy.init_node('phone_gps', anonymous=True)
        self.gps_pub = rospy.Publisher("/phone_gps/receiver_lla", NavSatFix, queue_size=10)
        
        self.HOST = '0.0.0.0'
        self.PORT = 1234
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        self.s.bind((self.HOST, self.PORT))
        self.s.listen(1)

        self.thread = threading.Thread(target=self.listen_network)
        self.thread.daemon = True
        self.thread.start()
        
        rospy.spin()


    def listen_network(self):
        while not rospy.is_shutdown():
            try:
                conn, addr = self.s.accept()
                rospy.loginfo("Connected by %s", addr)
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    # b'40.414306,116.677526\n'
                    # extract the latitude and longitude from the string
                    str_data = data.decode('utf-8').strip()
                    lat, lon = str_data.split(',')
                    lat = float(lat)
                    lon = float(lon)
                    gps_msg = NavSatFix()
                    gps_msg.header = Header()
                    gps_msg.header.stamp = rospy.Time.now()
                    gps_msg.header.frame_id = ''
                    gps_msg.latitude = lat
                    gps_msg.longitude = lon
                    gps_msg.altitude = 0.0
                    gps_msg.status.status = 1
                    gps_msg.status.service = 0
                    gps_msg.position_covariance = [0.0] * 9
                    gps_msg.position_covariance_type = 3
                    self.gps_pub.publish(gps_msg)
                conn.close()
            except Exception as e:
                rospy.logerr(f"Error: {e}")

if __name__ == '__main__':
    phone_gps = PhoneGPS()
