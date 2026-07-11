#!/usr/bin/env python
import re
from std_msgs.msg import String
from std_msgs.msg import Empty
from nvi_msgs.msg import HeaderString
import rospy
import zhtts
import sounddevice as sd
import time
import threading
import numpy as np
import edge_tts, playsound, tempfile

class AsyncRate:
    def __init__(self,rate) -> None:
        self.rate = rate
        self.delta_time = 1.0 / self.rate
        self.sync_time = time.perf_counter()
    
    def sleep(self):
        time_now = time.perf_counter()
        if time_now - self.sync_time >self.delta_time:
            self.sync_time = time_now
            return True
        return False
    

class TextFilter:
    def __init__(self) -> None:
        self.text_msg_buffer = []
        self.played_msg = {}
        self.played_delta_time = 15
        self.k1, self.k2 = 1, 1
    
    def append(self,text_msg):
        self.text_msg_buffer.append(text_msg)

    def update(self,stamp):
        priorities = []
        text_msg_buffer = self.text_msg_buffer.copy()
        self.text_msg_buffer = []
        for text_msg in text_msg_buffer:
            priority = 0
            text, text_stamp = text_msg.data, text_msg.header.stamp
            if text in self.played_msg and (stamp - self.played_msg[text]).to_sec() < self.played_delta_time:
                priority += self.k1 * (stamp - self.played_msg[text]).to_sec()
            else:
                priority = self.k1 * stamp.to_sec()
            priority += self.k2 * (stamp - text_stamp).to_sec()
            priorities.append(priority)
        max_idx = np.argmax(priorities)
        self.played_msg[text_msg_buffer[max_idx].data] = text_msg_buffer[max_idx].header.stamp
        return text_msg_buffer[max_idx].data
        


class NVIVoice:
    def __init__(self):
        rospy.init_node('nvi_voice', anonymous=True)
        self.DELTA_TIME = rospy.get_param("/voice/delta_time", default=3)  
        self.tts = zhtts.TTS()
        self.is_tts_work = threading.Semaphore(1)
        self.filter_rate = AsyncRate(5)
        self.text_filter = TextFilter()
        self.last_time = time.perf_counter()
        self.heartbeat_pub = rospy.Publisher("/voice/heartbeat", Empty, queue_size=10)
        rospy.Subscriber("/voice/nvi_voice_topic", String, self.tts_normal_voice_callback,queue_size=1)
        # rospy.Subscriber("/voice/navigation_interaction", String, self.tts_normal_voice_callback,queue_size=1)
        rospy.Subscriber("/global_planning/voice", String, self.tts_global_planning_callback, queue_size=1)
        rospy.Subscriber("/voice/system", String, self.tts_system_callback, queue_size=10)
        rospy.Subscriber("/voice/filter", HeaderString, self.tts_filter_callback, queue_size=1)
        self.system_pub = rospy.Publisher("/system/interaction", String, queue_size=10)
        self.global_planning_pub = rospy.Publisher("/global_planning/interaction", String, queue_size=10)
        self.semantic_pub = rospy.Publisher("/semantic/interaction", String, queue_size=10) 
        self.spin()

    def spin(self):
        self.voice_rate = rospy.Rate(10)
        while not rospy.is_shutdown():
            self.heartbeat_pub.publish(Empty())
            # if self.filter_rate.sleep():
            #     text = self.text_filter.update(rospy.Time.now())
            #     self.play(text)
            self.voice_rate.sleep()


    def system_interaction(self, msg):
        self.system_pub.publish(msg.data)

    def global_planning_interaction(self, msg):
        rospy.loginfo(rospy.get_caller_id()+" I heard %s", msg.data)
        words = msg.data.split('|')
        if len(words) < 3:
            rospy.loginfo("The number of the words should be 3.")
            return
        mode, action, description = words[0], words[1], words[2]

        if mode == 'G':
            if action == "":
                text = description
            else:
                text = description+", 请"+action
        else:
            rospy.loginfo("Illegalmode%s.", mode)
            return
        self.global_planning_pub.publish(text)

    # def tts_cmd_callback(self, msg):
    #     rospy.loginfo(rospy.get_caller_id()+" I heard %s", msg.data)
    #     words = msg.data.split('|')
    #     if len(words) < 3:
    #         rospy.loginfo("The number of thewords should be3.")
    #         return
    #     mode, action, description = words[0], words[1], words[2]

    #     if mode == 'H':
    #         text = action
    #     else:
    #         if time.perf_counter() - self.last_time < self.DELTA_TIME:
    #             return
    #         self.last_time = time.perf_counter()
    #         if mode == 'M':
    #             text = "前方检测到 "+words[2]+", 请"+action
    #         elif mode == 'L':
    #             text = description
    #         else:
    #             rospy.loginfo("Illegalmode%s.", mode)
    #             return
    #     self.play(text)

    def tts_global_planning_callback(self, msg):
        rospy.loginfo(rospy.get_caller_id()+" I heard %s", msg.data)
        words = msg.data.split('|')
        if len(words) < 3:
            rospy.loginfo("The number of the words should be 3.")
            return
        mode, action, description = words[0], words[1], words[2]

        if mode == 'G':
            if action == "":
                text = description
            else:
                text = description+", 请"+action
        else:
            rospy.loginfo("Illegalmode%s.", mode)
            return
        self.play(text)
    
    def tts_system_callback(self,msg):
        # rospy.loginfo(" I heard %s", msg.data, "time delay:", (rospy.Time.now()-msg.header.stamp).to_sec())
        self.play(msg.data, engine='zhtts')
        
    def tts_normal_voice_callback(self,msg):
        # rospy.loginfo(" I heard %s", msg.data)
        self.play(msg.data, engine='zhtts')
    
    def tts_filter_callback(self,msg):
        # Simply is the best
        # rospy.loginfo(" I heard %s", msg.data)
        self.play(msg.data)
        # self.text_filter.append(msg)

    def play(self,text, engine=None):
        rospy.loginfo(" I played %s", text)
        self.is_tts_work.acquire()

        if engine is None:
            engine = 'zhtts'
        
        # zhtts can't deal with english
        if re.search("[a-zA-Z]", text):
            engine = 'edge-tts'
        
        if engine == 'edge-tts':
            temp_file = tempfile.mktemp(suffix=".wav")
            communicate = edge_tts.Communicate(text, voice="zh-CN-YunjianNeural", rate="+50%")
            communicate.save_sync(temp_file)
            playsound.playsound(temp_file)
        elif engine == 'zhtts':
            audio = self.tts.synthesis(text)
            sd.play(audio, samplerate=28000)
            sd.wait()

        self.is_tts_work.release()
        # self.tts_work_status = False


if __name__ == '__main__':
    nvi_voice = NVIVoice()
