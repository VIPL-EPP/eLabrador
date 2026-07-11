#!/usr/bin/env python
import rospy, rosnode
from std_msgs.msg import String, Empty, Bool
# from src.asrt_sdk_ros import asrt_speech
from collections import deque
import dashscope
from dashscope.audio.asr import (Recognition, RecognitionCallback, RecognitionResult)
import pyaudio, time
import threading
import os
dashscope.api_key = os.environ.get("DASHSCOPE_API_KEY", "")

# class SpeechDeque():
#     def __init__(self,maxlen=2) -> None:
#         self.buffer = deque(maxlen=maxlen)
    
#     def append(self,str):
#         self.buffer.append(str)
    
#     def is_detected(self,str):
#         res = ''.join(self.buffer)
#         return str in res

#     def buffer2str(self):
#         return ''.join(self.buffer)

#     def clear_buffer(self):
#         self.buffer.clear()


# class CmdTable():
#     def __init__(self) -> None:
#         self.cmd_zh_check_table = dict()
#         self.cmd_pinyin_check_table = dict()
#         self.cmd_zh_list = []
#         self.cmd_pinyin_list = []

#     @staticmethod
#     def zh2pinyin(str):
#         res = pypinyin.pinyin(str,style=pypinyin.NORMAL)
#         res = [e[0] for e in res]
#         return ''.join(res)

#     def parse_json(self,filepath):
#         with open(filepath, encoding='utf-8') as file:
#             json_file = json.load(file)
#             for cmds in json_file:
#                 self.cmd_zh_list.append(cmds['cmd_zh'])
#                 cmd_pinyin = self.zh2pinyin(cmds['cmd_zh'])
#                 self.cmd_pinyin_list.append(cmd_pinyin)
#                 self.cmd_pinyin_check_table[cmd_pinyin]=cmds['cmd']
#                 self.cmd_zh_check_table[cmds['cmd_zh']]=cmds['cmd']

    
#     def check_pinyin_cmd(self,str):
#         for cmd in self.cmd_pinyin_list:
#             if cmd in str:
#                 return self.cmd_pinyin_check_table[cmd]
#         return None
    
#     def check_zh_cmd(self,str):
#         for cmd in self.cmd_zh_list:
#             if cmd in str:
#                 return self.cmd_zh_check_table[cmd]
#         return None

# class NVISpeech():
#     def __init__(self) -> None:
#         rospy.init_node('nvi_speech', anonymous=True)
#         self.pub_cmd = rospy.Publisher(
#             "/speech/command", String, queue_size=10)
#         self.voice_pub = rospy.Publisher(
#             "/voice/system", String, queue_size=10)
#         self.heartbeat_pub = rospy.Publisher("/speech/heartbeat", Empty, queue_size=10)    
#         self.asrt_speech  =ASRTSpeech(duration=4)
#         self.asrt_speech.open_audio()
#         self.buffer = SpeechDeque(maxlen=2)
#         self.cmd_table =CmdTable()
#         self.cmd_table.parse_json(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+"/config/speech_cmd_config.json")


#     def spin(self):
#         ress = []
#         while not rospy.is_shutdown():
#             self.heartbeat_pub.publish(Empty())
#             wave_data = self.asrt_speech.read_wave()
#             res,res_pinyin  = self.asrt_speech.recognize_speech(wave_data)
#             res_pinyin = [e[:-1] for e in res_pinyin]
#             res_pinyin = ''.join(res_pinyin)
#             self.buffer.append(res_pinyin)
#             cmd = self.cmd_table.check_pinyin_cmd(self.buffer.buffer2str())
#             # print('I heard:',self.buffer.buffer2str())
#             if cmd is not None:
#                  self.pub_cmd.publish(cmd)
#                  self.buffer.clear_buffer()
#                  self.voice_pub.publish("正在"+res)
#                  print('send cmd',cmd)
            

#         self.asrt_speech.close_audio()


class Callback(RecognitionCallback):
    def __init__(self) -> None:
        super().__init__()
        self.mic = None
        self.stream = None
        self.counter = 0
        self.msg_list = []

    def on_open(self) -> None:
        self.mic = pyaudio.PyAudio()
        self.stream = self.mic.open(
            format = pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True
        )
        print('RecognitionCallback open.')
    
    def on_error(self, result: RecognitionResult) -> None:
        print(result)
    
    def on_close(self) -> None:
        print('RecognitionCallback close.')

    def on_event(self, result: RecognitionResult) -> None:
        if result.get_sentence()['end_time'] is not None:
            text = result.get_sentence()['text']
            self.msg_list.append(text)
            self.counter += 1


class SpeechNode:
    def __init__(self) -> None:
        self.status = False
        self.pub_cmd = rospy.Publisher(
            "/speech/text", String, queue_size=10)
        self.heartbeat_pub = rospy.Publisher("/speech/heartbeat", Empty, queue_size=10)
        self.callback = Callback()
        self.recognition = Recognition(model='paraformer-realtime-v1',
                            format='pcm',
                            sample_rate=16000,
                            callback=self.callback)
        
    def spin(self) -> None:
        self.recognition.start()
        counter = 0
        while not rospy.is_shutdown():
            empty = Empty()
            self.heartbeat_pub.publish(empty)
            data = self.callback.stream.read(3200, exception_on_overflow=False)
            flag = False
            while not flag:
                try:
                    self.recognition.send_audio_frame(data)
                    while counter != self.callback.counter:
                        text = self.callback.msg_list[counter]
                        counter += 1
                        self.pub_cmd.publish(text)
                    flag = True
                except Exception as e:
                    if not self.recognition._running:
                        self.recognition.start()
            time.sleep(0.1)
        self.recognition.stop()
        self.callback.stream.stop_stream()
    

wait_flag = True
if __name__ == '__main__':
    # Record speech affect connection to belt, so waiting for belt first
    rospy.init_node('nvi_speech', anonymous=True)
    start_time = rospy.Time.now()
    wait_flag = True
    def call_back(msg):
        global wait_flag
        wait_flag=False
    while wait_flag and not rospy.is_shutdown():
        rospy.sleep(0.5)
        cur_tim = rospy.Time.now()
        if (cur_tim - start_time).to_sec() > 3:
            break
        nodes = rosnode.get_node_names()
        for name in nodes:
            if name == "/belt":
                sub = rospy.Subscriber("/belt/heartbeat", Empty, callback=call_back)
                while wait_flag and not rospy.is_shutdown():
                    rospy.sleep(0.5)
                sub.unregister()
                del sub
                break
        
        
    speechnode = SpeechNode()
    speechnode.spin()
    # thread = threading.Thread(target=speechnode.spin)
    # thread.start()
    # rospy.spin()
