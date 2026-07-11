#!/usr/bin/env python3
from std_msgs.msg import Empty, Bool
from nvi_msgs.msg import HeaderString
import bluetooth
import rospy
from collections import deque
SOCK_PORT = 1


class NVIBelt:
    def __init__(self):
        self.is_connected = False
        rospy.init_node('nvi_belt_bt', anonymous=True)
        self.heartbeat_pub = rospy.Publisher("/belt/heartbeat", Empty, queue_size=10)
        rospy.Subscriber("/keyboard_input", HeaderString, self.keyboard_callback, queue_size=10)
        self.receive_pub = rospy.Publisher('/belt_info', HeaderString, queue_size=10)
        rospy.Subscriber("/local_planning/belt", HeaderString, self.beltCallback,queue_size=1)
        rospy.Subscriber("/belt/traffic_mask", Bool, self.trafficMaskCallback,queue_size=1)
        self.actual_vibration = rospy.Publisher("/belt/actual_vibration", HeaderString, queue_size=10)
        self.bt_charac = None
        self.data_buffer =  deque(maxlen=10)
        self.command_mask = False
        self.BLUETOOTH_MAC_ADDR = rospy.get_param("/belt/bluetooth_mac_address", default="")
        if self.BLUETOOTH_MAC_ADDR is "":
            raise ValueError("The bluetooth MAC.address is not set.")
        self.last_sent_cmd = "000"
        self.last_published_cmd = "000"
        self.zero_start_time = None
        self.hold_duration = rospy.Duration(1.0)
        self.connect(self.BLUETOOTH_MAC_ADDR)
        self.spin()

    def spin(self):
        self.belt_rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            self.heartbeat_pub.publish(Empty())
            if self.is_connected is None or not len(self.data_buffer):
                continue

            command = self.data_buffer[-1]
            now = rospy.Time.now()
            send_cmd = command
            publish_cmd = command

            if command == "000":
                if self.last_sent_cmd != "000":
                    if self.zero_start_time is None:
                        self.zero_start_time = now
                    if now - self.zero_start_time < self.hold_duration:
                        send_cmd = self.last_sent_cmd
                        publish_cmd = self.last_sent_cmd
                    else:
                        send_cmd = "000"
                        publish_cmd = "000"
                        self.last_sent_cmd = "000"
                        self.zero_start_time = None
                else:
                    send_cmd = "000"
                    publish_cmd = "000"
            else:
                if command != self.last_sent_cmd:
                    self.last_sent_cmd = command
                self.zero_start_time = None
                send_cmd = command
                publish_cmd = command

            try:
                self.bt_charac.send(bytes('$' + send_cmd, encoding='utf-8'))
                if publish_cmd != self.last_published_cmd:
                    msg = HeaderString()
                    msg.header.stamp = now
                    msg.data = publish_cmd
                    self.actual_vibration.publish(msg)
                    self.last_published_cmd = publish_cmd
            except Exception:
                self.is_connected = False
                rospy.logwarn("The Connection with device %s terminated unexpectedly.", self.BLUETOOTH_MAC_ADDR)
                rospy.logwarn("Retrying connect to device %s.", self.BLUETOOTH_MAC_ADDR)
                self.connect(self.BLUETOOTH_MAC_ADDR)
                msg = HeaderString()
                msg.header.stamp = rospy.Time.now()
                msg.data = "000"
                self.actual_vibration.publish(msg)
                self.last_published_cmd = "000"
                self.last_sent_cmd = "000"
                self.zero_start_time = None

            self.data_buffer.clear()
            self.data_buffer.append("000")
            self.belt_rate.sleep()
        try:
            self.bt_charac.send(bytes('$'+'000', encoding='utf-8'))
        except Exception:
            pass

    def beltCallback(self,msg):
        # print("Belt TIME",msg.header.stamp.to_time(),rospy.get_rostime().to_time())
        if self.command_mask:
            self.data_buffer.append("000")
        else:
            self.data_buffer.append(msg.data)

    def keyboard_callback(self, msg):
        data = msg.data
        # print(data)
        if data == 'a':
            self.data_buffer.append('041')
        elif data=='d':
            self.data_buffer.append('021')
        elif data=='s':
            self.data_buffer.append('051')
        elif data=='q':
            self.data_buffer.append('031')
        elif data=='e':
            self.data_buffer.append('011')
    
    def trafficMaskCallback(self,msg):
        self.command_mask = True if msg.data else False

    def connect(self,BLUETOOTH_MAC_ADDR):
        self.bt_charac = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        while not rospy.is_shutdown():
            nearby_devices = bluetooth.discover_devices(duration=3)
            if BLUETOOTH_MAC_ADDR in nearby_devices:
                rospy.loginfo("Found device %s successfully.", BLUETOOTH_MAC_ADDR)
                break
            rospy.loginfo("Not found device %s.", BLUETOOTH_MAC_ADDR)
            rospy.loginfo("Nearby Devices:\n"+"\n".join(nearby_devices))
        connect_rate = rospy.Rate(0.5) 
        while not self.is_connected and not rospy.is_shutdown():
            try:
                self.bt_charac.connect((BLUETOOTH_MAC_ADDR, SOCK_PORT))
                rospy.loginfo("Connect to device %s successfully.", BLUETOOTH_MAC_ADDR)
                self.is_connected = True
            except:
                rospy.loginfo("Connect to device %s failed.", BLUETOOTH_MAC_ADDR)
            connect_rate.sleep()


if __name__ == '__main__':
    nvi_belt = NVIBelt()
