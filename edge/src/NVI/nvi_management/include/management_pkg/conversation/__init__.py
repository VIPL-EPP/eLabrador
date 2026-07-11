import rospy
from std_msgs.msg import String, Header
from nvi_msgs.msg import HeaderString
from threading import Thread, Lock
from openai import OpenAI
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge, CvBridgeError
import base64, io
import os
import PIL.Image
from management_pkg.utils import remove_punctuation
import dimsim


api_key = os.environ.get("OPENAI_API_KEY", "")
base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

class OpenAIVQA:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    def __call__(self, messages, model='gpt-4o', image_detail='low') -> str:
        parsed_messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT
            }
        ]
        for message in messages:
            parsed_message = {
                "role": message["role"],
                "content": [
                    {"type": "text", "text": message["content"]},
                ],
            }
            parsed_messages.append(parsed_message)
        
        if 'image' in messages[-1]:
            image = messages[-1]['image']
            base64_image = self.encode_image(image, image_detail)
            parsed_messages[-1]['content'].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": image_detail, # high, low, auto，两种分辨率
                },
            })
        
        response = self.client.chat.completions.create(
            model=model,
            messages=parsed_messages,
        )
        response, usage = response.choices[0].message.content, response.usage
        return response
    
    @staticmethod
    def encode_image(image, image_detail):
        '''encode image to base64
        :param image: PIL Image
        :param image_detail: image detail (high, low, auto)
        :return: base64 image

        low: 512x512
        high: 
        '''
        image = PIL.Image.fromarray(image, mode='RGB')
        if image_detail == 'low':
            image = image.resize((512, 512))
        else:
            min_edge = min(image.size)
            max_edge = max(image.size)
            ratio = min(768 / min_edge, 2000 / max_edge)
            image = image.resize((int(image.size[0] * ratio), int(image.size[1] * ratio)))
        img_stream = io.BytesIO()
        image.save(img_stream, format="JPEG")
        img_stream.seek(0)
        img_bytes = img_stream.read()
        base64_image = base64.b64encode(img_bytes).decode('utf-8')
        return base64_image
    
    SYSTEM_PROMPT = '''You are a visual question and answer assistance system for blind people. Your task is to generate response to user's instruction.
You should keep your response as short as possible. Just follow the instuction or answer the question.
You need to be careful to recognize if the blind person is giving you instructions or asking questions, if not you don't need to output anything.
'''

class ConversationController:
    def __init__(self) -> None:
        self.conversation_user_pub = rospy.Publisher("/conversation/user", HeaderString, queue_size=1)
        self.conversation_assistant_pub = rospy.Publisher("/conversation/assistant", HeaderString, queue_size = 10)
        self.voice_pub = rospy.Publisher("/voice/nvi_voice_topic", String, queue_size = 10)
        self.bridge = CvBridge()
        self.messages = list()
        self.messages_limit = 20
        self.ondeal = Lock()
        self.conversation = OpenAIVQA()
    
    def check_conversation(self, text: str) -> bool:
        text = remove_punctuation(text)
        return len(text) > 2 and dimsim.get_distance(text[:2], "同学") < 1
    
    def __call__(self, key_msg_table, user_input):
        thread = Thread(target=self.deal, args=(key_msg_table, user_input))
        thread.start()
        return
    
    def deal(self, key_msg_table, user_input):
        if not self.check_avaliable_input(user_input):
            return
        if not self.ondeal.acquire(blocking=False):
            self.voice_pub.publish("正在处理上一句话")
            return
        try:
            image = self.try_to_find_image(key_msg_table)
            self.messages.append({
                "role": "user",
                "content": user_input,
                "image": image
            })
            if len(self.messages) > self.messages_limit:
                self.messages = self.messages[self.messages_limit//2:]
            response = self.conversation(self.messages)


            self.messages.append({
                "role": "assistant",
                "content": response
            })
            self.conversation_assistant_pub.publish(Header(stamp=rospy.get_rostime), response)
            self.voice_pub.publish(response)
        except Exception as e:
            rospy.logerr("[Conversation Error] {} raised when generate response.".format(str(e)))
            self.voice_pub.publish("错误，无法回答")

        self.ondeal.release()
        return
    
    def try_to_find_image(self, key_msg_table):
        msg_list = key_msg_table.key_msg_list
        for idx, msg in enumerate(msg_list):
            if "/camera/rgb/image_raw" in msg.msg:
                color_img_ros = key_msg_table.last_check[idx][1]
                try:
                    if isinstance(color_img_ros, Image):
                        image = self.bridge.imgmsg_to_cv2(color_img_ros, "rgb8")
                    else:
                        assert isinstance(color_img_ros, CompressedImage)
                        image = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "rgb8")
                except CvBridgeError as e:
                    pass
                return image
        return None
    
    def check_avaliable_input(self, user_input):
        if len(user_input) > 5:
            return True
        special_check_list = ['你好', '？', '?', '什么']
        for x in special_check_list:
            if x in user_input:
                return True
        return False
