#!/usr/bin/env python3
from std_msgs.msg import String
from bluepy.btle import Scanner, Peripheral
import rospy
from collections import deque



class NVIBelt:
    def __init__(self):
        rospy.init_node('nvi_belt', anonymous=True)
        rospy.Subscriber("/local_planning/belt", String, self.beltCallback,queue_size=1)
        self.ble_charac = None
        self.data_buffer =  deque(maxlen=10)
        self.BLUETOOTH_MAC_ADDR = rospy.get_param("/belt/bluetooth_mac_address", default="")
        if self.BLUETOOTH_MAC_ADDR == "":
            raise ValueError("The bluetooth MAC.address is not set.")
        while not rospy.is_shutdown():
            try:
                self.connection = Peripheral(self.BLUETOOTH_MAC_ADDR)
                rospy.loginfo("connect to device %s successfully.", self.BLUETOOTH_MAC_ADDR)
            except:
                rospy.loginfo("Not found device %s.", self.BLUETOOTH_MAC_ADDR)
        characteristics = self.connection.getCharacteristics()
        self.ble_charac  = characteristics[3]
        self.spin()

    def spin(self):
        self.belt_rate = rospy.Rate(1)
        while not rospy.is_shutdown():
            if self.ble_charac is None or not len(self.data_buffer):
                continue
            self.ble_charac.write(bytes('$'+self.data_buffer[-1], encoding='utf-8'))
            # print("write", self.data_buffer[-1])
            # rospy.loginfo("write %s",self.data_buffer[-1])
            self.data_buffer.clear()
            self.data_buffer.append("000")

            self.belt_rate.sleep()
        self.ble_charac.send(bytes('$'+"000", encoding='utf-8'))
        


    def beltCallback(self,msg):
        self.data_buffer.append(msg.data)


if __name__ == '__main__':
    nvi_belt = NVIBelt()
