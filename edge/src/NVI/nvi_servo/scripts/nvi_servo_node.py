#!/usr/bin/env python3
import rospy
import tf
from object_servo.object_servo import ObjectServo
from nvi_msgs.msg import HeaderString
from std_msgs.msg import String
from nav_msgs.msg import Odometry
import json
import numpy as np


class NVIServo(ObjectServo):
    def __init__(self) -> None:
        super().__init__()
        rospy.init_node('nvi_servo_node', anonymous=True)
        self.parameter_init()
        self.publish_init()
        self.landmark_sub = rospy.Subscriber("/servo/landmark", HeaderString, self.landmark_sub,queue_size=1)
        self.global_status_sub = rospy.Subscriber("/global_planning/status",String,self.global_status_callback,queue_size=10)
        self.subscribe()
        self.spin()

    def spin(self):
        rospy.spin()
    
    def parameter_init(self):
        self.is_work = True
        self.is_found = False
        self.target_object_name = 'AMD'#'向科学家致敬'
        self.object_update_time = None
        self.reset_object(self.target_object_name)
        self.toward_count = 0
        self.TOWARD_THRESHOLD = 10

    def publish_init(self):
        self.belt_pub = rospy.Publisher(
            "/local_planning/belt", HeaderString, queue_size=10)
        self.voice_pub = rospy.Publisher("/voice/system", String, queue_size=10)
        self.cmd_pub = rospy.Publisher("/voice/filter", HeaderString, queue_size=10)
        self.status_pub = rospy.Publisher("/nvi_navigation/status", String, queue_size=10)
    
    def subscribe(self):
        self.text_obejcts_sub =  rospy.Subscriber("/ocr", HeaderString,self.text_callback, queue_size=10)
        self.vio_sub = rospy.Subscriber("/vins_estimator/odometry", Odometry,self.vio_callback, queue_size=1)

    def unsubscribe(self):
        self.text_obejcts_sub.unregister()
        self.vio_sub.unregister()
    
    def text_callback(self,msg):
        objects_json = json.loads(msg.data)
        objects = []
        for obj in objects_json:
            x,y,z,text,confidence = obj
            objects.append({'position':np.array([x,y,z]),'text':text})
            print(text)
        if not objects:
            rospy.loginfo('Empty text list found.')
            return 
        is_found = self.update(objects)
        if is_found:
            self.object_update_time = msg.header.stamp
        self.is_found = is_found or self.is_found
        
    def vio_callback(self, msg):
        if not self.is_found:
            rospy.loginfo('Target object searching.')
            start_msg = HeaderString()
            start_msg.data = '请原地转圈并根据腰带振动方向调整朝向'
            start_msg.header = msg.header
            self.cmd_pub.publish(start_msg)
            self.belt_pub.publish(HeaderString(data='011',header=msg.header))
            return
        if (self.object_update_time - msg.header.stamp).to_sec() > 10: # sec
            self.is_found = False
            rospy.loginfo('The target object has not been updated for more than 30 seconds.')
            return
        location = (msg.pose.pose.position.x, msg.pose.pose.position.y,msg.pose.pose.position.z)
        direction = self.quaternion2yaw(msg.pose.pose.orientation)
        theta_yaw = self.pursuit_yaw(direction,location)
        if theta_yaw is None:
            rospy.loginfo('Multiple target objects are found.')
        cmd = self.theta2cmd(theta_yaw)
        # print(cmd)
        self.belt_pub.publish(HeaderString(data=cmd,header=msg.header))

        if abs(theta_yaw) >10:
            self.toward_count = 0
            return
        else:
            rospy.loginfo('左右方位对准目标开始调整上下方位')
            self.toward_count +=1
        # TODO test function
        direction = self.quaternion2pitch(msg.pose.pose.orientation)
        theta_pitch = self.pursuit_pitch(direction, location)
        if abs(theta_pitch) >10:
            pitch_msg = HeaderString()
            pitch_msg.data = '请稍向上抬头' if theta_pitch>0 else '请稍向下低头'
            pitch_msg.header = msg.header
            # self.voice_pub.publish(pitch_msg)
            self.cmd_pub.publish(pitch_msg)
            # print(pitch_msg)
        if abs(theta_pitch) <10 and self.toward_count > self.TOWARD_THRESHOLD:
            # self.voice_pub.publish('已朝向目标地导航结束')
            end_msg = HeaderString()
            # end_msg.data = '已朝向目标地导航结束'
            end_msg.data = '已调整至目标朝向，本次导航结束，感谢您的使用'
            end_msg.header = msg.header
            self.cmd_pub.publish(end_msg)
            rospy.loginfo('已朝向目标地导航结束')
            self.status_pub.publish("arrived")
    
    def landmark_sub(self, msg):
        self.target_object_name = msg.data
        self.is_found = False
        self.object_update_time = None
        self.reset_object(self.target_object_name)
        rospy.loginfo('Set the landmark as '+self.target_object_name+'.')
        
    def global_status_callback(self,msg):
        if msg.data =='arrived' and self.is_work is False:
            self.is_work = True
            self.is_found = False
            self.reset_object(self.target_object_name)
            self.subscribe()
        if msg.data != 'arrived' and self.is_work is True:
            self.is_work = False
            self.is_found = False
            self.unsubscribe()
        
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
    def quaternion2yaw(quaternion):
        '''
        return the yaw in cartesian system. (x, y)
        '''
        # x right, y forward, z up.
        (p, r, y) = tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
        direction  = (-np.sin(y),np.cos(y))
        # direction  = (np.cos(y),np.sin(y))
        return direction
    
    @staticmethod
    def quaternion2pitch(quaternion):
        '''
        return the pitch in cartesian system. (x, y)
        '''
        # x right, y forward, z up.
        (p, r, y) = tf.transformations.euler_from_quaternion([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
        # print('pitch',np.degrees(p))
        direction  = (-np.sin(p),np.cos(p))
        return direction
    
if __name__ == "__main__":
    nvi_servo = NVIServo()