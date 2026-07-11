#!/usr/bin/env python
import rospy
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge, CvBridgeError
import cv2
import numpy as np
import message_filters
from dynamic_reconfigure.client import Client as DynamicReconfigureClient

class NVIAutoExposure:
    def __init__(self):
        rospy.init_node('nvi_auto_exposure', anonymous=True)
        self.brightness_threshould = rospy.get_param("/nvi_auto_exposure/brightness_threshould", default=200)
        self.area_threshould = rospy.get_param("/nvi_auto_exposure/area_threshould", default=100)
        self.scale_factor = rospy.get_param("/nvi_auto_exposure/scale_factor", default=0.5)
        self.client = DynamicReconfigureClient('/camera/rgb_camera/auto_exposure_roi')
        
        self.bridge = CvBridge()
        color_img_type = CompressedImage if rospy.get_param('/nvi_auto_exposure/compressed_image', default=False) else Image
        self.img_pub_topic = rospy.get_param("/nvi_auto_exposure/image_publish_topic", default=False)
        self.image_sub_topic = rospy.get_param('/nvi_auto_exposure/color_image_topic')
        self.image_sub_topic += '/compressed' if color_img_type is CompressedImage else ''
        self.color_sub = message_filters.Subscriber(self.image_sub_topic, color_img_type, queue_size = 1, buff_size = 30*480*640)
        self.color_sub.registerCallback(self.callback)
        if self.img_pub_topic:
            self.img_pub = rospy.Publisher(self.img_pub_topic, Image, queue_size = 10)
        
        rospy.spin()
    
    def callback(self, color_img_ros):
        header = color_img_ros.header
        try:
            if isinstance(color_img_ros, Image):
                image = self.bridge.imgmsg_to_cv2(color_img_ros, "rgb8")
            else:
                assert isinstance(color_img_ros, CompressedImage)
                image = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "rgb8")
        except CvBridgeError as e:
            print(e)
        
        # find connected components for intensity > threshould
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        threshould = self.brightness_threshould
        _, mask = cv2.threshold(gray, threshould, 255, cv2.THRESH_BINARY)
        mask = cv2.erode(mask, np.ones((9,9), np.uint8), iterations=1)
        mask = cv2.dilate(mask, np.ones((9,9), np.uint8), iterations=1)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
        
        # find the largest connected component
        max_area = 0
        max_idx = 0
        for i in range(num_labels):
            pos_a, pos_b = np.where(labels==i)
            val = mask[pos_a[0], pos_b[0]]
            if val == 0:
                continue
            area = stats[i, 4]
            if area > max_area:
                max_area = area
                max_idx = i
        # plot the largest bbox on the image
        im_h, im_w = image.shape[:2]
        image = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        if max_area < self.area_threshould:
            x, y, w, h = 0, 0, 639, 100 
        if max_area >= self.area_threshould:
            x, y, w, h = stats[max_idx, :4]
        if self.img_pub_topic:
            cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
        center = (int(x+w/2), int(y+h/2))
        w, h = int(w*self.scale_factor), int(h*self.scale_factor)
        x, y = int(center[0]-w/2), int(center[1]-h/2)
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x+w >= im_w:
            w=im_w-x-1
        if y+h >= im_h:
            h=im_h-y-1
        if self.img_pub_topic:
            cv2.rectangle(image, (x, y), (x+w, y+h), (255, 0, 0), 2)
            image_msg = self.bridge.cv2_to_imgmsg(image, "rgb8")
            image_msg.header = header
            self.img_pub.publish(image_msg)
            
        self.client.update_configuration({'left': x, 'top': y, 'right': x+w, 'bottom': y+h})


if __name__ == '__main__':
    nvi_auto_exposure = NVIAutoExposure()
