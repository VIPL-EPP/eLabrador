#!/usr/bin/env python3
import rospy
from std_msgs.msg import String
import json5 as json
import dimsim
from .conversation import ConversationController
from .navigation import NavigationController
from .utils import CONFIG_DIR, remove_punctuation


class Msg():
    def __init__(self,msg_:str,package_:str,type_:str,name_zh_:str):
        self.msg = msg_
        self.package = package_
        self.type = type_
        self.name_zh = name_zh_
    
class KeyMsgTable():
    def __init__(self) -> None:
        self.key_msg_list = []
        self.sensor_msg_list = []
        self.function_msg_list = []
        self.sub_list = []
        self.last_check = []


    def parse_json(self,filepath):
        with open(filepath, encoding='utf-8') as file:
            json_file = json.load(file)
            sensor_msgs =  json_file["sensor"]
            function_msgs =  json_file["function"]
            for msgs in sensor_msgs:
                msg = Msg(msgs["msg"],msgs["msg_package"],msgs["msg_type"],msgs["msg_name_zh"])
                self.sensor_msg_list.append(msg)
            for msgs in function_msgs:
                msg = Msg(msgs["msg"],msgs["msg_package"],msgs["msg_type"],msgs["msg_name_zh"])
                self.function_msg_list.append(msg)
            self.key_msg_list = self.sensor_msg_list+self.function_msg_list
    

    def status_callback(self, idx):
        msg = self.key_msg_list[idx]
        def check_func(rosdata):
            self.last_check[idx] = (rospy.get_rostime(), rosdata)
        return check_func
    

    def subscribe_status_topics(self):
        msg_list = self.key_msg_list
        self.last_check = [(rospy.Time.from_sec(0), None)] * len(self.key_msg_list)
        for idx, msg in enumerate(msg_list):
            exec("from "+msg.package+" import "+msg.type)
            sub = eval("rospy.Subscriber(msg.msg, "+msg.type+", self.status_callback(idx),queue_size=1)")
            self.sub_list.append(sub)
    

    def status_check(self, pub=None, except_pub=None, DEFAULT_DURATION=5.0):
        if pub is not None:
            rospy.loginfo("Start checking system status.")
        SYSTEM_OK = True
        error_msgs = list()
        for idx, msg in enumerate(self.key_msg_list):
            last_check_duration = (rospy.get_rostime() - self.last_check[idx][0]).to_sec()
            msg_ok = (last_check_duration <= DEFAULT_DURATION)
            if not msg_ok:
                system_loginfo = msg.name_zh + "工作异常"
                SYSTEM_OK = False
                error_msgs.append(msg)
                if except_pub is not None:
                    except_pub.publish(system_loginfo)
                    rospy.loginfo(system_loginfo)
            else:
                system_loginfo = msg.name_zh + "工作正常"
            if pub is not None:
                rospy.loginfo(system_loginfo)
                pub.publish(system_loginfo)
        if pub is not None:
            rospy.loginfo("Finish checking system status.")
        return SYSTEM_OK, error_msgs


class NVIManagement:
    def __init__(self):        
        self.system_pub = rospy.Publisher("/management/command",String,queue_size=10)
        self.voice_pub = rospy.Publisher("/voice/system", String, queue_size=10)

        self.speech_sub =  rospy.Subscriber("/speech/text",String,self.speech_callback,queue_size=10)

        key_msg_path = rospy.get_param("/nvi_management/key_msg_path", default=CONFIG_DIR+"/key_msg.json")
        self.key_msg_table = KeyMsgTable()
        self.key_msg_table.parse_json(key_msg_path)
        self.key_msg_table.subscribe_status_topics()

        self.conversation_controller = ConversationController()
        self.navigation_controller = NavigationController(self.key_msg_table)
        
        # first check
        self.voice_pub.publish("系统启动中")
        while not rospy.is_shutdown():
            SYSTEM_OK, error_msgs = self.key_msg_table.status_check(DEFAULT_DURATION=5.0)
            print("System Checking", SYSTEM_OK)
            rospy.logerr("Error Messages: "+",".join([msg.name_zh for msg in error_msgs]))
            if SYSTEM_OK:
                break
            rospy.sleep(0.5)
        self.voice_pub.publish("系统启动完成")

        DEFAULT_DURATION = 5.0
        rate = rospy.Rate(1/DEFAULT_DURATION)
        while not rospy.is_shutdown():
            self.key_msg_table.status_check(except_pub=self.voice_pub, DEFAULT_DURATION=5.0)
            rate.sleep()

    # @staticmethod
    # def battery_check(pub,threshold=20):
    #     battery = psutil.sensors_battery()
    #     if battery is None:
    #         return
    #     if not battery.power_plugged and battery.percent < threshold:
    #         rospy.logwarn("Battery low.")
    #         pub.publish("系统电池电量低请充电")
    
    def speech_callback(self, msg):
        text = msg.data
        rospy.loginfo(text+" speech reveived.")
        pure_words = remove_punctuation(text)
        try:
            if len(pure_words)>=2 and dimsim.get_distance(pure_words[:2], "启动")<1:
                rospy.loginfo("启动")
            elif len(pure_words)>=2 and dimsim.get_distance(pure_words[:2], "关闭")<1:
                rospy.loginfo("关闭")
            elif self.navigation_controller.check_set_destination(text):
                rospy.loginfo("Set Destination: "+text)
                flag, response = self.navigation_controller.set_destination(text)
                if len(response) > 0:
                    self.voice_pub.publish(response)
            elif self.conversation_controller.check_conversation(text):
                rospy.loginfo("Conversation: "+text)
                self.conversation_controller(self.key_msg_table, text)
        except Exception as e:
            rospy.logerr(str(e))
