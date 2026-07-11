#!/usr/bin/env python
"""
Take in an image (rgb or rgb-d)
Use CNN to do semantic segmantation
Out put a cloud point with semantic color registered
\author Xuan Zhang
\date May - July 2018
"""

from __future__ import division
from __future__ import print_function
from audioop import add
# from traffic_light.yolo import YOLO
from std_msgs.msg import String
from nvi_msgs.msg import stamp_float32array, RGBDImage, CompressedRGBDImage, HeaderString
import sys
import os
import json
# numpy multithreading caused that ros subscriber thread runs slow.
# Set number of threads in numpy as 1, to decrease ros messag delay.
# os.environ["OMP_NUM_THREADS"] = "1" 

from matplotlib.pyplot import cla
import rospy
from sensor_msgs.msg import Image, CompressedImage
from geometry_msgs.msg import Point, PointStamped
from cv_bridge import CvBridge, CvBridgeError
import traceback

import numpy as np

from sensor_msgs.msg import PointCloud2
from color_pcl_generator import PointType, ColorPclGenerator
import genpy
from nvi_msgs.msg import stamp_float32array, RGBDImage, CompressedRGBDImage
import message_filters
import time
from multiprocessing import Queue, Process
from queue import Empty
# from queue import Empty, Queue
import threading

# from skimage.transform import resize
import cv2
import tf2_geometry_msgs
from geometry_msgs.msg import Point, PointStamped
import tf2_ros

# import torch

class RealtimeFilter:
    def __init__(self, processor, gap_limit=0.1):
        self.queue = Queue()
        # self.subprocess = Process(target=self.deal, args=(processor, True), daemon=False)
        # self.subprocess.start()
        rospy.init_node('semantic_cloud')

        # self.gap_limit = gap_limit
        # rospy.init_node('semantic_cloud')
        self.tf_buffer = tf2_ros.Buffer(cache_time=rospy.Duration(10))
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        self.subprocess = threading.Thread(target=self.deal, args=(processor, False))
        self.subprocess.daemon = True
        self.subprocess.start()
    
    def ros_call_back(self, *args, **kwargs):
        # print("receive data from ros")
        try:
            while not self.queue.empty():
                self.queue.get_nowait()
        except Empty:
            pass
        # print("write data")

        world_frame_id = 'world'
        image_frame_id = 'camera_link'
        transform_to_world=None
        if self.tf_buffer is not None:
            try:
                transform_to_world = self.tf_buffer.lookup_transform(world_frame_id, image_frame_id, args[0].header.stamp, rospy.Duration(0.3))
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
                rospy.logwarn("Cannot find transform from {} to {} in 0.2s".format(image_frame_id, world_frame_id))
        kwargs['transform_to_world'] = transform_to_world
        self.queue.put((args, kwargs))
        # time.sleep(0)
    
    def deal(self, processor, rosinit):
        if rosinit:
            rospy.init_node('semantic_subprocess', anonymous=True, argv=("semantic_subprocess.py",))
        processor.init()
        try:
            while True:
                args, kwargs = self.queue.get()
                # realtime_check = True
                # for v in args:
                #     if isinstance(v, genpy.Message) and hasattr(v, 'header'):
                #         if (rospy.Time.now() - args[0].header.stamp).to_sec() > self.gap_limit:
                #             realtime_check = False
                #             break
                # if not realtime_check:
                #     time.sleep(0)
                #     continue

                processor(*args, **kwargs)
                # time.sleep(0)
        except Exception:
            # traceback.print_exc()
            exit(0)

class SemanticCloud:
    """
    Class for ros node to take in a color image (bgr) and do semantic segmantation on it to produce an image with semantic class colors (chair, desk etc.)
    Then produce point cloud based on depth information
    CNN: PSPNet (https://arxiv.org/abs/1612.01105) (with resnet50) pretrained on ADE20K, fine tuned on SUNRGBD or not
    """
    def __init__(self, gen_pcl = True):
        """
        Constructor
        \param gen_pcl (bool) whether generate point cloud, if set to true the node will subscribe to depth image
        """
        self.filter = RealtimeFilter(SemanticCloudWorker(gen_pcl, 
                                                         rospy.get_param('/semantic_pcl/rgbd_topic') is not False, 
                                                         rospy.get_param('/semantic_pcl/compressed_rgbd')))
        # Get point type
        point_type = rospy.get_param('/semantic_pcl/point_type')
        if point_type == 0:
            self.point_type = PointType.COLOR
            print('Generate color point cloud.')
        elif point_type == 1:
            self.point_type = PointType.SEMANTICS_MAX
            print('Generate semantic point cloud [max fusion].')
        elif point_type == 2:
            self.point_type = PointType.SEMANTICS_BAYESIAN
            print('Generate semantic point cloud [bayesian fusion].')
        else:
            print("Invalid point type.", point_type, type(point_type), point_type==0, point_type==1, point_type==2)
            return
        # Set up ROS
        print('Setting up ROS...')
        # Set up ros image subscriber
        # Set buff_size to average msg size to avoid accumulating delay
        
        if gen_pcl:
            # Point cloud frame id
            frame_id = rospy.get_param('/semantic_pcl/frame_id')
            self.frame_id = frame_id
            if rospy.get_param('/semantic_pcl/rgbd_topic'):
                message_type = CompressedRGBDImage if rospy.get_param('/semantic_pcl/compressed_rgbd') else RGBDImage
                self.sub = message_filters.Subscriber(rospy.get_param('/semantic_pcl/rgbd_topic'), message_type, queue_size = 1, buff_size = 80*480*640)
                self.sub.registerCallback(self.filter.ros_call_back)
            elif rospy.get_param('/semantic_pcl/compressed_color_image_topic'):
                self.color_sub = message_filters.Subscriber(rospy.get_param('/semantic_pcl/compressed_color_image_topic'), CompressedImage, queue_size = 1, buff_size = 30*480*640)
                self.depth_sub = message_filters.Subscriber(rospy.get_param('/semantic_pcl/depth_image_topic'), Image, queue_size = 1, buff_size = 40*480*640 ) # increase buffer size to avoid delay (despite queue_size = 1)
                self.ts = message_filters.ApproximateTimeSynchronizer([self.color_sub, self.depth_sub], queue_size = 1, slop = 0.1) # Take in one color image and one depth image with a limite time gap between message time stamps
                self.ts.registerCallback(self.filter.ros_call_back)
            else:
                self.color_sub = message_filters.Subscriber(rospy.get_param('/semantic_pcl/color_image_topic'), Image, queue_size = 1, buff_size = 30*480*640)
                self.depth_sub = message_filters.Subscriber(rospy.get_param('/semantic_pcl/depth_image_topic'), Image, queue_size = 1, buff_size = 40*480*640 ) # increase buffer size to avoid delay (despite queue_size = 1)
                self.ts = message_filters.ApproximateTimeSynchronizer([self.color_sub, self.depth_sub], queue_size = 1, slop = 0.1) # Take in one color image and one depth image with a limite time gap between message time stamps
                self.ts.registerCallback(self.filter.ros_call_back)
        else:
            self.image_sub = rospy.Subscriber(rospy.get_param('/semantic_pcl/color_image_topic'), Image, self.filter.ros_call_back, queue_size = 1, buff_size = 30*480*640)
        print('Main process ready.')



class SemanticCloudWorker:
    """
    Class for ros node to take in a color image (bgr) and do semantic segmantation on it to produce an image with semantic class colors (chair, desk etc.)
    Then produce point cloud based on depth information
    CNN: PSPNet (https://arxiv.org/abs/1612.01105) (with resnet50) pretrained on ADE20K, fine tuned on SUNRGBD or not
    """
    def __init__(self, gen_pcl = True, rgbd = False, compressed_rgbd = False):
        self.gen_pcl = gen_pcl
        self.rgbd = rgbd
        self.compressed_rgbd = compressed_rgbd
    
    def init(self):
        """
        Constructor
        \param gen_pcl (bool) whether generate point cloud, if set to true the node will subscribe to depth image
        """
        
        from blind_guide_modules import build_detector
        # Get point type
        point_type = rospy.get_param('/semantic_pcl/point_type')
        if point_type == 0:
            self.point_type = PointType.COLOR
            print('[subprocess] Generate color point cloud.')
        elif point_type == 1:
            self.point_type = PointType.SEMANTICS_MAX
            print('[subprocess] Generate semantic point cloud [max fusion].')
        elif point_type == 2:
            self.point_type = PointType.SEMANTICS_BAYESIAN
            print('[subprocess] Generate semantic point cloud [bayesian fusion].')
        else:
            print("[subprocess] Invalid point type.", point_type, type(point_type), point_type==0, point_type==1, point_type==2)
            return
        # Get image size
        self.img_width, self.img_height = rospy.get_param('/camera/width'), rospy.get_param('/camera/height')
        # Set up CNN is use semantics
        if self.point_type is not PointType.COLOR:
            print('[subprocess] Setting up CNN model...')
            # Set device
            # self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            # Get dataset
            self.dataset = rospy.get_param('/semantic_pcl/dataset')
            self.model_name = rospy.get_param('/semantic_pcl/model_name')
            # Setup model
            if self.dataset in ['mapillary', 'cityscapes']:
                import os
                src_path = os.path.dirname(__file__)
                self.n_classes = 66 # Semantic class number
                self.instance_format = rospy.get_param('/semantic_pcl/instance_format', None)
                self.model = build_detector(self.model_name, self.dataset, src_path=src_path)
        # Declare array containers
        if self.point_type is PointType.SEMANTICS_BAYESIAN:
            self.semantic_colors = np.zeros((3, self.img_height, self.img_width, 3), dtype = np.uint8) # Numpy array to store 3 decoded semantic images with highest confidences
            self.confidences = np.zeros((3, self.img_height, self.img_width), dtype = np.float32) # Numpy array to store top 3 class confidences
        # Set up ROS
        print('[subprocess] Setting up ROS...')
        self.bridge = CvBridge() # CvBridge to transform ROS Image message to OpenCV image
        # Semantic image publisher
        self.sem_img_pub = rospy.Publisher("/semantic_pcl/semantic_image", Image, queue_size = 1)
        self.conf_img_pub = rospy.Publisher("/semantic_pcl/confidence_image", Image, queue_size = 1)
        # Set up ros image subscriber
        # Set buff_size to average msg size to avoid accumulating delay
        if self.gen_pcl:
            # Point cloud frame id
            frame_id = rospy.get_param('/semantic_pcl/frame_id')
            self.frame_id = frame_id
            # Camera intrinsic matrix
            fx = rospy.get_param('/camera/fx')
            fy = rospy.get_param('/camera/fy')
            cx = rospy.get_param('/camera/cx')
            cy = rospy.get_param('/camera/cy')
            intrinsic = np.matrix([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype = np.float32)
            self.intrinsic = intrinsic
            self.pcl_pub = rospy.Publisher("/semantic_pcl/semantic_pcl", PointCloud2, queue_size = 1)
            if hasattr(self, 'model_name') and self.model_name == 'custom' and self.instance_format:
                # assert self.instance_format == 'bbox3d'
                self.instance_pub = rospy.Publisher("/semantic_pcl/instances", stamp_float32array, queue_size=1)
                pass
            self.cloud_generator = ColorPclGenerator(intrinsic, self.img_width, self.img_height, frame_id , self.point_type)
        print('[subprocess] Ready.')

        # MODEL_PATH = 'models/LytNetV1_weights'
        # self.LYTnet = LYTNet()
        # checkpoint = torch.load(MODEL_PATH)
        # self.LYTnet.load_state_dict(checkpoint)
        # self.LYTnet.eval()
        # self.LYTnet = self.LYTnet.to(self.device)
        # self.classes = {'0':'red', '1':'green', '2':'none', '3':'countdown_blank', '4':'countdown_green'}
        # self.order = 0
        
        # TODO: move to cloud or run in cpu
        # self.yolo = YOLO()
        # self.intrinsic_IT = np.matrix([[fx, 0., cx],
        #                                [0., fy, cy],
        #                                [0., 0., 1.]]).I.T
        # self.world_frame_id = 'world'
        # self.img_frame_id = 'camera_link'  
        # self.tf_buffer = tf2_ros.Buffer(cache_time=rospy.Duration(10))
        # self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)
        # self.traffic_pub = rospy.Publisher('/semantic_pcl/traffic', HeaderString, queue_size = 10)
        # self.traffic_sub = rospy.Subscriber('/semantic_pcl/traffic', HeaderString, self.test_callback)
        
    def test_callback(self, msg):
        
        print(msg.data)

    def __call__(self, *args, **kwargs):
        if self.gen_pcl:
            if self.rgbd:
                self.rgbd_callback(*args, **kwargs)
            else:
                # TODO: move to cloud or run in cpu
                self.traffic_callback(*args, **kwargs)
                self.color_depth_callback(*args, **kwargs)
        else:
            self.color_callback(*args, **kwargs)

    def rgbd_callback(self, rgbd_ros):
        self.color_depth_callback(rgbd_ros.rgb, rgbd_ros.depth, stamp=rgbd_ros.header.stamp)
    
    # def color_callback(self, color_img_ros):
    #     """
    #     Callback function for color image, de semantic segmantation and show the decoded image. For test purpose
    #     \param color_img_ros (sensor_msgs.Image) input ros color image message
    #     """
    #     try:
    #         if isinstance(color_img_ros, Image):
    #             color_img = self.bridge.imgmsg_to_cv2(color_img_ros, "bgr8") # Convert ros msg to numpy array
    #         else:
    #             assert isinstance(color_img_ros, CompressedImage)
    #             color_img = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "bgr8") # Convert ros msg to numpy array
    #     except CvBridgeError as e:
    #         print(e)
    #     # Do semantic segmantation
    #     class_probs = self.predict(color_img)
    #     if isinstance(class_probs, tuple):
    #         decoded, confidence, additional = class_probs
    #     else:
    #         confidence, label = class_probs.max(1)
    #         confidence, label = confidence.squeeze(0).numpy(), label.squeeze(0).numpy()
    #         label = resize(label, (self.img_height, self.img_width), order = 0, mode = 'reflect', anti_aliasing=False, preserve_range = True) # order = 0, nearest neighbour
    #         label = label.astype(np.int)
    #         # Add semantic class colors
    #         decoded = decode_segmap(label, self.n_classes, self.cmap)        # Show input image and decoded image
    #         confidence = resize(confidence, (self.img_height, self.img_width),  mode = 'reflect', anti_aliasing=True, preserve_range = True)
    #     cv2.imshow('Camera image', color_img)
    #     cv2.imshow('confidence', confidence)
    #     cv2.imshow('Semantic segmantation', decoded)
    #     cv2.waitKey(3)
        

    def traffic_callback(self, color_img_ros, depth_img_ros, stamp=None, transform_to_world=None):
        """
        Callback function to produce point cloud registered with semantic class color based on input color image and depth image
        \param color_img_ros (sensor_msgs.Image) the input color image (bgr8)
        \param depth_img_ros (sensor_msgs.Image) the input depth image (registered to the color image frame) (float32) values are in millimeter
        """
        # TODO: move to cloud or run in cpu
        return
        # with open("logs/semantic.txt", "a") as f:
        #     f.write(f"begin: {(rospy.Time.now()-color_img_ros.header.stamp).to_sec()}\n")
        # Convert ros Image message to numpy array
        try:
            if isinstance(color_img_ros, Image):
                color_img = self.bridge.imgmsg_to_cv2(color_img_ros, "bgr8")
            else:
                assert isinstance(color_img_ros, CompressedImage)
                color_img = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "bgr8")
        except CvBridgeError as e:
            print(e)
        if stamp is None:
            stamp = color_img_ros.header.stamp
         
        # ##ac##    
        # #Do traffic detection
        # traffic_light = self.traffic_detection(color_img)
        # self.order = self.order + 1
        # print(self.order)
        # print(traffic_light)
        # if traffic_light == 'red' or traffic_light == 'countdown_blank':
        #     print("检测到红灯")
        # if traffic_light == 'green' or traffic_light == 'countdown_green':
        #     print("检测到绿灯")
        
        traffic = self.yolo.detect_image(color_img, crop = False, count=False)
        try:
            transform = self.tf_buffer.lookup_transform(self.world_frame_id, self.img_frame_id, color_img_ros.header.stamp, rospy.Duration(0.3))
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            rospy.logwarn("Cannot find transform from {} to {} in 0.3s".format(color_img_ros.header.frame_id, self.world_frame_id))
            return
        traffic_pub_res = list()
        if traffic is not None:
            for line in traffic:
                box = np.array(line[0])
                txt = line[1]
                score = line[2]
                # calculate center of box as joint point of two diagonal lines
                inter = self.seg_intersect(box[0], box[2], box[1], box[3])
                if depth_img_ros is None:
                    depth_img = np.ones((color_img.shape[0], color_img.shape[1]), dtype=np.float32)
                else:
                    depth_img = self.bridge.imgmsg_to_cv2(depth_img_ros, "32FC1") / 1000
                try:
                    depth = depth_img[int(inter[1]), int(inter[0])]
                except:
                    depth = 100
                depth = np.clip(depth, 0.1, 100)
                points = np.array([inter[0], inter[1], 1.0]) * depth
                points = points.reshape(1,3)@(self.intrinsic_IT) * 1.0
                point = Point(points[0, 0], points[0, 1], points[0, 2])
                ros_point = PointStamped(header=color_img_ros.header, point=point)
                point = tf2_geometry_msgs.do_transform_point(ros_point, transform).point
                traffic_pub_res.append([point.x, point.y, point.z, txt, score])
            traffic_pub_msg = json.dumps(traffic_pub_res)
            print(traffic_pub_msg)
            traffic_pub_msg_ros = HeaderString(header=color_img_ros.header, data=traffic_pub_msg)
            traffic_pub_msg_ros.header.frame_id = self.world_frame_id
            self.traffic_pub.publish(traffic_pub_msg_ros)
        
        ##ac##    

    def color_depth_callback(self, color_img_ros, depth_img_ros, stamp=None, transform_to_world=None):
        """
        Callback function to produce point cloud registered with semantic class color based on input color image and depth image
        \param color_img_ros (sensor_msgs.Image) the input color image (bgr8)
        \param depth_img_ros (sensor_msgs.Image) the input depth image (registered to the color image frame) (float32) values are in millimeter
        """
        # with open("logs/semantic.txt", "a") as f:
        #     f.write(f"begin: {(rospy.Time.now()-color_img_ros.header.stamp).to_sec()}\n")
        # Convert ros Image message to numpy array
        try:
            if isinstance(color_img_ros, Image):
                color_img = self.bridge.imgmsg_to_cv2(color_img_ros, "bgr8")
            else:
                assert isinstance(color_img_ros, CompressedImage)
                color_img = self.bridge.compressed_imgmsg_to_cv2(color_img_ros, "bgr8")
            depth_img = self.bridge.imgmsg_to_cv2(depth_img_ros, "32FC1")
        except Exception as e:
            print(e)
        if stamp is None:
            stamp = color_img_ros.header.stamp
        # Resize depth
        assert depth_img.shape[0] == self.img_height and depth_img.shape[1] == self.img_width
         
        # ##ac##    
        # #Do traffic detection
        # traffic_light = self.traffic_detection(color_img)
        # self.order = self.order + 1
        # print(self.order)
        # print(traffic_light)
        # if traffic_light == 'red' or traffic_light == 'countdown_blank':
        #     print("检测到红灯")
        # if traffic_light == 'green' or traffic_light == 'countdown_green':
        #     print("检测到绿灯")
        
        # traffic = self.yolo.detect_image(color_img, crop = False, count=False)
        # try:
        #     transform = self.tf_buffer.lookup_transform(self.world_frame_id, self.img_frame_id, color_img_ros.header.stamp, rospy.Duration(0.3))
        # except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
        #     rospy.logwarn("Cannot find transform from {} to {} in 0.3s".format(color_img_ros.header.frame_id, self.world_frame_id))
        # traffic_pub_res = list()
        # if traffic is not None:
        #     print(traffic)
        #     for line in traffic:
        #         box = np.array(line[0])
        #         txt = line[1]
        #         score = line[2]
        #         # calculate center of box as joint point of two diagonal lines
        #         inter = self.seg_intersect(box[0], box[2], box[1], box[3])
        #         if depth_img_ros is None:
        #             depth_img = np.ones((color_img.shape[0], color_img.shape[1]), dtype=np.float32)
        #         else:
        #             depth_img = self.bridge.imgmsg_to_cv2(depth_img_ros, "32FC1") / 1000
        #         try:
        #             depth = depth_img[int(inter[1]), int(inter[0])]
        #         except:
        #             depth = 100
        #         depth = np.clip(depth, 0.1, 100)
        #         points = np.array([inter[0], inter[1], 1.0]) * depth
        #         points = points.reshape(1,3)@(self.intrinsic_IT) * 1.0
        #         point = Point(points[0, 0], points[0, 1], points[0, 2])
        #         ros_point = PointStamped(header=color_img_ros.header, point=point)
        #         point = tf2_geometry_msgs.do_transform_point(ros_point, transform).point
        #         traffic_pub_res.append([point.x, point.y, point.z, txt, score])
        #     print(traffic_pub_res)
        # traffic_pub_msg = json.dumps(traffic_pub_res)
        # print(traffic_pub_msg)
        # traffic_pub_msg_ros = HeaderString(header=color_img_ros.header, data=traffic_pub_msg)
        # traffic_pub_msg_ros.header.frame_id = self.world_frame_id
        # self.traffic_pub.publish(traffic_pub_msg_ros)
        
        # ##ac##    

        if self.point_type is PointType.COLOR:
            cloud_ros = self.cloud_generator.generate_cloud_color(color_img, depth_img, stamp)
        else:
            # Do semantic segmantation
            if self.point_type is PointType.SEMANTICS_MAX:
                try:
                    semantic_color, pred_confidence, additional = self.predict_max(color_img, depth_img, transform_to_world=transform_to_world)
                except:
                    return
                cloud_ros = self.cloud_generator.generate_cloud_semantic_max(color_img, depth_img, semantic_color, pred_confidence, stamp)
                if additional is not None and len(additional)>0:
                    # instance info
                    outputdata = list()
                    for instance in additional['instances']:
                        outputdata.append(float(instance['id']))
                        if isinstance(instance['data'], np.ndarray):
                            instance['data'] = [instance['data']]
                        for data in instance['data']:
                            outputdata.append(float(data.size))
                            outputdata.extend(list(data.reshape(-1)))
                    instance_ros = stamp_float32array(header=cloud_ros.header, data=outputdata)
                    instance_ros.header.stamp = stamp
                    self.instance_pub.publish(instance_ros)

            elif self.point_type is PointType.SEMANTICS_BAYESIAN:
                assert False
                self.predict_bayesian(color_img)
                # Produce point cloud with rgb colors, semantic colors and confidences
                cloud_ros = self.cloud_generator.generate_cloud_semantic_bayesian(color_img, depth_img, self.semantic_colors, self.confidences, stamp)

            # Publish semantic image
            if self.sem_img_pub.get_num_connections() > 0:
                if self.point_type is PointType.SEMANTICS_MAX:
                    semantic_color_msg = self.bridge.cv2_to_imgmsg(semantic_color, encoding="bgr8", header=cloud_ros.header)
                else:
                    semantic_color_msg = self.bridge.cv2_to_imgmsg(self.semantic_colors[0], encoding="bgr8", header=cloud_ros.header)
                self.sem_img_pub.publish(semantic_color_msg)
                conf_image = (np.clip(pred_confidence, 0, 1) * 255).astype(np.uint8)
                conf_image_msg = self.bridge.cv2_to_imgmsg(conf_image, encoding="mono8", header=cloud_ros.header)
                self.conf_img_pub.publish(conf_image_msg)

        # Publish point cloud
        self.pcl_pub.publish(cloud_ros)
        # with open("logs/semantic.txt", "a") as f:
        #     f.write(f"pub: {(rospy.Time.now()-color_img_ros.header.stamp).to_sec()}\n")
            
    def seg_intersect(self,a1,a2, b1,b2) :
        da = a2-a1
        db = b2-b1
        dp = a1-b1
        dap = self.perp(da)
        denom = np.dot(dap, db)
        num = np.dot(dap, dp)
        return (num / denom.astype(float))*db + b1
    
    def perp(self, a) :
        b = np.empty_like(a)
        b[0] = -a[1]
        b[1] = a[0]
        return b

    def predict_max(self, img, depth, transform_to_world=None):
        """
        Do semantic prediction for max fusion
        \param img (numpy array rgb8)
        """
        return self.predict(img, depth, transform_to_world=transform_to_world)

    def predict_bayesian(self, img):
        assert False, "Doesn't support baysian predict yet"

        """
        Do semantic prediction for bayesian fusion
        \param img (numpy array rgb8)
        """
        class_probs = self.predict(img)
        # Take 3 best predictions and their confidences (probabilities)
        pred_confidences, pred_labels  = torch.topk(input = class_probs, k = 3, dim = 1, largest = True, sorted = True)
        pred_labels = pred_labels.squeeze(0).cpu().numpy()
        pred_confidences = pred_confidences.squeeze(0).cpu().numpy()
        # Resize predicted labels and confidences to original image size
        for i in range(pred_labels.shape[0]):
            pred_labels_resized = resize(pred_labels[i], (self.img_height, self.img_width), order = 0, mode = 'reflect', anti_aliasing=False, preserve_range = True) # order = 0, nearest neighbour
            pred_labels_resized = pred_labels_resized.astype(np.int)
            # Add semantic class colors
            self.semantic_colors[i] = decode_segmap(pred_labels_resized, self.n_classes, self.cmap)
        for i in range(pred_confidences.shape[0]):
            self.confidences[i] = resize(pred_confidences[i], (self.img_height, self.img_width),  mode = 'reflect', anti_aliasing=True, preserve_range = True)

    def predict(self, img, depth=None, transform_to_world=None):
        """
        Do semantic segmantation
        \param img: (numpy array bgr8) The input cv image
        """
        # rescale depth 
        if depth is not None:
            depth = depth * 0.001
        img = img.copy() # Make a copy of image because the method will modify the image
        #orig_size = (img.shape[0], img.shape[1]) # Original image size
        return self.model.predict(img, color='bgr', depth=depth, transform_matrix=self.intrinsic, instance_pred=self.instance_format, transform_to_world=transform_to_world)
    
    ##ac##    
    # def traffic_detection(self, img):
    #     """
    #     Do traffic_detection
    #     \param img: (numpy array bgr8) The input cv image
    #     """
    #     with torch.no_grad():
    #         image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #         image = cv2.resize(image, [768, 576])
    #         image = torch.FloatTensor(image)
    #         image = image.permute(2, 0, 1).unsqueeze(0)
    #         image = image.to(self.device)
    #         pred_classes, pred_direc = self.LYTnet(image)
    #         _, predicted = torch.max(pred_classes, 1)
    #         #incorrect prediction
    #         predicted_idx = str(predicted.cpu().numpy()[0])
    #         return self.classes[predicted_idx]
        
    ##ac##    

def main(args):
    seg_cnn = SemanticCloud(gen_pcl = True)
    rospy.spin()
    # seg_cnn.filter.subprocess.kill()
    seg_cnn.filter.queue.put(None)
    print("[Semantic main process] Shutting down")
    print("[Subprocess state]", seg_cnn.filter.subprocess.is_alive())

if __name__ == '__main__':
    main(sys.argv)
