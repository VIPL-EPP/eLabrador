#!/usr/bin/env python3
"""Model-free OCR placeholder that keeps the ROS topic graph alive."""

import json

import rospy
from sensor_msgs.msg import Image
from nvi_msgs.msg import HeaderString


class NVIOCRDummyNode:
    def __init__(self):
        rospy.init_node("nvi_ocr_dummy", anonymous=True)
        image_topic = rospy.get_param("~image_topic", "/camera/color/image_raw")
        output_topic = rospy.get_param("~output_topic", "/ocr")
        self.default_text = rospy.get_param("~default_text", "")
        self.pub = rospy.Publisher(output_topic, HeaderString, queue_size=10)
        self.sub = rospy.Subscriber(image_topic, Image, self.on_image, queue_size=1)
        rospy.loginfo("nvi_ocr_dummy subscribed to %s and publishes %s", image_topic, output_topic)

    def on_image(self, msg):
        out = HeaderString()
        out.header = msg.header
        out.data = json.dumps([{"text": self.default_text, "score": 0.0, "point": []}])
        self.pub.publish(out)


if __name__ == "__main__":
    NVIOCRDummyNode()
    rospy.spin()
