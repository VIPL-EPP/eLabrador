#!/usr/bin/env python
from std_msgs.msg import String
import rospy
from paddleocr import PaddleOCR, draw_ocr
from nvi_msgs.msg import stamp_float32array, RGBDImage, CompressedRGBDImage, HeaderString
from sensor_msgs.msg import Image, CompressedImage
import tf2_geometry_msgs
from geometry_msgs.msg import Point, PointStamped
import tf2_ros
from cv_bridge import CvBridge, CvBridgeError
import cv2
import numpy as np
import tqdm
import time
import message_filters
import json
import roslib
import logging

def perp(a) :
    b = np.empty_like(a)
    b[0] = -a[1]
    b[1] = a[0]
    return b

# line segment a given by endpoints a1, a2
# line segment b given by endpoints b1, b2
# return
def seg_intersect(a1,a2, b1,b2) :
    da = a2-a1
    db = b2-b1
    dp = a1-b1
    dap = perp(da)
    denom = np.dot(dap, db)
    num = np.dot(dap, dp)
    return (num / denom.astype(float))*db + b1

class NVIOCR:
    def __init__(self):
        rospy.init_node('nvi_ocr', anonymous=True)
        self.lang = rospy.get_param("/nvi_ocr/lang", default='ch')
        self.use_gpu = rospy.get_param("/nvi_ocr/use_gpu", default=True)
        self.switch_topic = rospy.get_param("/nvi_ocr/switch_config/topic_name", default='/global_planning/status')
        self.run_msg = rospy.get_param("/nvi_ocr/switch_config/start_string", default='arrived')
        self.pub_topic = rospy.get_param("/nvi_ocr/publish_topic", default='/ocr')
        self.img_pub_topic = rospy.get_param("/nvi_ocr/ocr_image_publish_topic", default=False)
        self.image_sub_topic = rospy.get_param('/nvi_ocr/color_image_topic')
        self.depth_sub_topic = rospy.get_param('/nvi_ocr/depth_image_topic')
        self.world_frame_id = rospy.get_param('/nvi_ocr/world_frame_id', default='world')
        self.img_frame_id = rospy.get_param('/nvi_ocr/img_frame_id', default='camera_link')
        self.pub_freq = rospy.get_param('/nvi_ocr/publish_frequency', default='detected_only')
        assert self.pub_freq in ['detected_only', 'all']
        debug_msg = rospy.get_param('/nvi_ocr/debug', default=False)
        if not debug_msg:
            logging.disable(logging.DEBUG)
        fx = rospy.get_param("/nvi_ocr/camera/fx")
        fy = rospy.get_param("/nvi_ocr/camera/fy")
        cx = rospy.get_param("/nvi_ocr/camera/cx")
        cy = rospy.get_param("/nvi_ocr/camera/cy")
        self.intrinsic_IT = np.matrix([[fx, 0., cx],
                                       [0., fy, cy],
                                       [0., 0., 1.]]).I.T
        
        # transform_matrix = np.matrix([[393.955,   0.   , 328.337],
        #                             [  0.   , 393.955, 238.703],
        #                             [  0.   ,   0.   ,   1.   ]]).I.T
        
        self.working = False
        self.bridge = CvBridge()
        self.model=PaddleOCR(use_angle_cls=True, lang=self.lang, use_gpu=self.use_gpu)
        self.switch_sub = rospy.Subscriber(self.switch_topic, String, self.switch_callback)
        color_img_type = CompressedImage if rospy.get_param('/nvi_ocr/compressed_image', default=True) else Image
        self.image_sub_topic += '/compressed' if color_img_type is CompressedImage else ''
        self.color_sub = message_filters.Subscriber(self.image_sub_topic, color_img_type , queue_size = 1, buff_size = 30*480*640)
        self.depth_sub = message_filters.Subscriber(self.depth_sub_topic, Image, queue_size = 1, buff_size = 40*480*640) # increase buffer size to avoid delay (despite queue_size = 1)
        self.rgbd_sub = message_filters.ApproximateTimeSynchronizer([self.color_sub, self.depth_sub], queue_size = 1, slop = 0.1) # Take in one color image and one depth image with a limite time gap between message time stamps
        self.tf_buffer = tf2_ros.Buffer(cache_time=rospy.Duration(10))
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        self.ocr_pub = rospy.Publisher(self.pub_topic, HeaderString, queue_size = 10)
        if self.img_pub_topic:
            self.img_pub = rospy.Publisher(self.img_pub_topic, Image, queue_size = 10)
        
        # warmup
        print("warm up...")
        img = np.random.uniform(0, 255, [480, 640, 3]).astype(np.uint8)
        for i in range(10):
            start_time = time.time()
            res = self.model.ocr(img, cls=True)
            end_time = time.time()
            print(f"[{i+1}/{10}] warm up time: ", end_time - start_time)
        print("module on ready.")

        rospy.spin()

    def switch_callback(self, msg):
        if msg.data == self.run_msg:
            if not self.working:
                rospy.loginfo("OCR start.")
                self.rgbd_sub.registerCallback(self.callback)
                self.working = True
        else:
            if self.working:
                rospy.loginfo("OCR stop.")
                self.rgbd_sub.callbacks.clear()
                self.working = False
    
    def callback(self, color_img_ros, depth_img_ros):
        header = color_img_ros.header
        try:
            if isinstance(color_img_ros, Image):
                image = self.bridge.imgmsg_to_cv2(color_img_ros, "rgb8")
            else:
                assert isinstance(color_img_ros, CompressedImage)
                image = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "rgb8")
            if depth_img_ros is None:
                depth_img = np.ones((image.shape[0], image.shape[1]), dtype=np.float32)
            else:
                depth_img = self.bridge.imgmsg_to_cv2(depth_img_ros, "32FC1") / 1000
        except CvBridgeError as e:
            print(e)
        result = self.model.ocr(image)[0]
        if len(result) == 0 and self.pub_freq == 'detected_only':
            return
        try:
            transform = self.tf_buffer.lookup_transform(self.world_frame_id, self.img_frame_id, header.stamp, rospy.Duration(0.3))
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            rospy.logwarn("Cannot find transform from {} to {} in 0.3s".format(header.frame_id, self.world_frame_id))
            return
        pub_res = list()
        for line in result:
            box = np.array(line[0]) # 4x2, 4 coners
            txt = line[1][0]
            score = line[1][1]
            # calculate center of box as joint point of two diagonal lines
            inter = seg_intersect(box[0], box[2], box[1], box[3])
            try:
                depth = depth_img[int(inter[1]), int(inter[0])]
            except:
                depth = 100
            depth = np.clip(depth, 0.1, 100)
            points = np.array([inter[0], inter[1], 1.0]) * depth
            points = points.reshape(1,3)@(self.intrinsic_IT) * 1.0
            point = Point(points[0, 0], points[0, 1], points[0, 2])
            ros_point = PointStamped(header=header, point=point)
            point = tf2_geometry_msgs.do_transform_point(ros_point, transform).point
            pub_res.append([point.x, point.y, point.z, txt, score])
        pub_msg = json.dumps(pub_res)
        pub_msg_ros = HeaderString(header=color_img_ros.header, data=pub_msg)
        pub_msg_ros.header.frame_id = self.world_frame_id
        self.ocr_pub.publish(pub_msg_ros)
        
        if self.img_pub_topic:
            boxes = [line[0] for line in result]
            txts = [line[1][0] for line in result]
            scores = [line[1][1] for line in result]
            font_path = roslib.packages.get_pkg_dir("nvi_ocr") + "/scripts/simfang.ttf"
            im_show = draw_ocr(image, boxes, txts, scores, font_path=font_path)
            img_ros = self.bridge.cv2_to_imgmsg(im_show, "rgb8", header=color_img_ros.header)
            self.img_pub.publish(img_ros)
        return

if __name__ == '__main__':
    nvi_ocr = NVIOCR()
