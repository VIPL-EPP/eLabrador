#!/usr/bin/env python
import rospy
import json
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
import message_filters
import jsonlines

class DataCollector:
    def __init__(self):
        rospy.init_node('data_collector', anonymous=True)

        # 定义消息过滤器，使用时间戳对齐
        odom_sub = message_filters.Subscriber('/vins_estimator/odometry', Odometry)
        imu_sub = message_filters.Subscriber('/camera/imu', Imu)
        rospy.Subscriber('/vins_estimator/odometry', Odometry, self.odo_test)
        rospy.Subscriber('/camera/imu', Imu, self.imu_test)
        self.ts = message_filters.TimeSynchronizer([odom_sub, imu_sub], 2000)
        self.ts.registerCallback(self.callback)

    def callback(self, odometry_msg, imu_msg):
        print(11)
        # data = {
        #     'odometry': {
        #         'linear_velocity': odometry_msg.twist.twist.linear,
        #         'angular_velocity': odometry_msg.twist.twist.angular,
        #         'position': odometry_msg.pose.pose.position,
        #         'orientation': odometry_msg.pose.pose.orientation
        #     },
        #     'imu': {
        #         'linear_acceleration': imu_msg.linear_acceleration,
        #         'angular_velocity': imu_msg.angular_velocity
        #     }
        # }
        # print(data)
        # self.save_data(data)

    def odo_test(self, odometry_msg):
        rospy.logwarn(odometry_msg.header.stamp)
        data = {
                'linear_velocity_x': odometry_msg.twist.twist.linear.x,
                'linear_velocity_y': odometry_msg.twist.twist.linear.y,
                'linear_velocity_z': odometry_msg.twist.twist.linear.z,
                'position_x': odometry_msg.pose.pose.position.x,
                'position_y': odometry_msg.pose.pose.position.y,
                'position_z': odometry_msg.pose.pose.position.z,
            }
        print(data)
        file = jsonlines.open('good1.jsonl', 'a')
        jsonlines.Writer.write(file, data)
        file.close()

    def imu_test(self, imu_msg):
        print(imu_msg.header.stamp)
    
    def save_data(self, data):
        with open('bad1.json', 'a') as json_file:
            json.dump(data, json_file)
        rospy.loginfo("Data saved to data.json")

if __name__ == '__main__':
    try:
        collector = DataCollector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass