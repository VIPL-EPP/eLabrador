# Copyright (c) Facebook, Inc. and its affiliates.
# Copied from: https://github.com/facebookresearch/detectron2/blob/master/demo/predictor.py
import json, io, requests
import threading
import os
import time

import numpy as np
import PIL.Image
import zlib
import pickle

import tf2_geometry_msgs
from geometry_msgs.msg import Point, PointStamped
import websocket
import ssl



def get_road_plane(points):
    # ransac
    n = 20
    rets = np.zeros((n, 5), dtype=np.float32)
    for _ in range(n):
        idx = np.random.choice(len(points), 3)
        p1, p2, p3 = points[idx]
        v1 = p2 - p1
        v2 = p3 - p1
        normal = np.cross(v1, v2)
        if np.linalg.norm(normal) < 1e-4:
            continue    
        normal /= np.linalg.norm(normal)
        d = -np.dot(normal, p1)
        inliers = np.abs(np.dot(points, normal) + d) < 0.1
        rets[_] = np.array([np.sum(inliers), normal[0], normal[1], normal[2], d], dtype=np.float32)
    return rets


class Detector(object):
    def __init__(self, device=None, debug_mode=False, src_path=None):
        """
        Single Detector
        config_path: path to config file
        model_path: path to model weights, override the model_path in config file
        device: 'cpu' or 'cuda:0' ..., if device is None, it will be set to 'cuda' when cuda is avaliable
        """
        self._debug_mode = debug_mode

        data_config_path = "configs/dataconfig_mapillary.json"
        if src_path:
            data_config_path = os.path.join(src_path, data_config_path)
        dataset_meta = json.load(open(data_config_path, "r"))

        self.categories = dataset_meta["labels"][:-1]
        self.metadata_colors = np.array([ x['color'] for x in self.categories ]).astype(np.uint8)
        self.road_available_categories_mask = np.array([c["available_on_ground"] for c in self.categories], dtype=np.bool_)
        self.road_determine_categories_mask = np.array(["construction--flat" in self.categories[c]["name"] or "marking--" in self.categories[c]["name"] for c in range(len(self.categories))], dtype=np.bool_)

        self.walkable_idx = list()
        for cid in range(len(self.categories)):
            if "pedestrian-area" in self.categories[cid]['name']:
                self.walkable_idx.append(cid)
                self.pedestrain_area_idx = cid
            elif "sidewalk" in self.categories[cid]['name']:
                self.walkable_idx.append(cid)
                self.sidewalk_idx = cid
            elif "crosswalk-zebra" in self.categories[cid]['name']:
                self.walkable_idx.append(cid)
    
    def _mapillary_get_road_mask(self, depth, transform_matrix, transform_to_world=None):
        points_mask = (depth > 0.1)
        y_int, x_int = points_mask.nonzero()
        x = x_int.astype(np.float32)
        y = y_int.astype(np.float32)
        points = np.stack((x, y, np.ones_like(x)), axis=-1) * depth[points_mask].reshape(-1, 1)
        points = points@(transform_matrix.I.T) * 1.0
        points = np.array(points, dtype=np.float32)

        # cid = np.argmax(sem_seg, axis=-1)
        # cid = cid[points_mask]
        # road_mask = road_determine_categories_mask[cid] & (depth[points_mask] < 10.0)
        road_mask = depth[points_mask] < 10.0
        road_points = points[road_mask]
        road_planes = get_road_plane(road_points)
        road_plane_id = np.argmax(road_planes[:, 0])
        road_rate = road_planes[road_plane_id, 0]/len(road_points)
        road_plane = (road_planes[road_plane_id, 1:4], road_planes[road_plane_id, 4])

        if transform_to_world is not None:

            camera_point = Point(0, 0, 0)
            camera_point = PointStamped(point=camera_point)
            camera_point = tf2_geometry_msgs.do_transform_point(camera_point, transform_to_world).point
            camera_point = np.array([camera_point.x, camera_point.y, camera_point.z])
            
            normal_point = Point(road_plane[0][0], road_plane[0][1], road_plane[0][2])
            normal_point = PointStamped(point=normal_point)
            normal_point = tf2_geometry_msgs.do_transform_point(normal_point, transform_to_world).point
            normal_point = np.array([normal_point.x, normal_point.y, normal_point.z])
            normal_dir = normal_point - camera_point

            # print("world normal dot:", np.abs(np.dot(normal_dir, np.array([0, 0, 1])) / np.linalg.norm(normal_dir)))

            if np.abs(np.dot(normal_dir, np.array([0, 0, 1])) / np.linalg.norm(normal_dir)) < 0.71:
                return None
        elif road_rate < 0.6:
            return None

        road_plane_mask = np.zeros_like(depth, dtype=np.bool_)
        road_plane_mask[points_mask] = np.abs(np.dot(points, road_plane[0]) + road_plane[1]) < 0.1

        return road_plane_mask
    
    def _mapillary_post_process(self, sem_seg, depth, transform_matrix, transform_to_world=None):
        road_plane_mask = self._mapillary_get_road_mask(depth, transform_matrix, transform_to_world)
        sem_seg[road_plane_mask] *= self.road_available_categories_mask.reshape(1, -1)
        sem_seg[road_plane_mask, self.sidewalk_idx] += sem_seg[road_plane_mask, self.pedestrain_area_idx]


        return sem_seg, road_plane_mask
    
    def model_inference(self, image: np.ndarray, road_mask: np.ndarray = None) -> np.ndarray:
        '''
        param: 
            image: RGB
        return:
            probs: np.ndarray (65, h, w)
        '''
        url = os.environ.get("MASK2FORMER_HTTP_URL")
        image = PIL.Image.fromarray(image)
        files = dict()
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=50)
        files['image'] = buffer.getvalue()

        # road_mask = None
        if road_mask is not None and False:
            buffer = io.BytesIO()
            np.savez_compressed(buffer, road_mask)
            files['road_mask'] = buffer.getvalue()
        response = requests.post(url, files=files, data={"return_probs": False}, timeout=2)
        buffer = io.BytesIO(response.content)
        response = np.load(buffer, allow_pickle=True)
        mask, conf = response['mask'], response['conf']
        # response_dict = pickle.loads(zlib.decompress(response.content))
        # mask = response_dict.pop('sem_mask')
        # conf = response_dict.pop('sem_conf')
        conf = conf.astype(np.float32) / 255.0
        return mask, conf, {}

    def predict(self, image, color='bgr', return_color=True, depth=None, transform_matrix=None, instance_pred='mask', transform_to_world=None):
        # print("depth", depth.shape, depth.dtype, type(depth), depth.min(), depth.max())
        # print("transform_matrix", depth.shape, transform_matrix)
        assert not instance_pred
        if color.lower() == 'bgr':
            image = image[:,:,::-1]
	
        if depth is not None:
            try:
                road_plane_mask = self._mapillary_get_road_mask(depth, transform_matrix, transform_to_world=transform_to_world)
            except:
                road_plane_mask = None
        else:
            road_plane_mask = None

        if self._debug_mode:
            start = time.perf_counter()
        cls_map, conf_map, additional = self.model_inference(image, road_plane_mask)
        if self._debug_mode:
            forward = time.perf_counter()
            # with open("logs/test_delay.txt", "a") as f:
            #     f.write(f"{forward-start}\n")
            print("forward:", forward-start)

        if road_plane_mask is not None:
            for wid in self.walkable_idx:
                conf_map[(cls_map==wid) & road_plane_mask] *= 10

        if return_color:
            colored_map = np.zeros(cls_map.shape+(3,), dtype=np.uint8)
            for cid in np.unique(cls_map):
                colored_map[cls_map==cid] = self.metadata_colors[cid:cid+1]
            return colored_map, conf_map, additional
        print("get", cls_map.shape)
        return cls_map, conf_map, additional
        
        

class Detector_WS(Detector):
    # uri = "wss://aicloud.conestore.cn:30013/inference/aicloud-visfmod-aicloud/nvi-server/mask2former/predict_ws"
    proxy_config = {
        # "http_proxy_host": "127.0.0.1",
        # "http_proxy_port": 1080,
        # "proxy_type": "socks5"
    }
    def __init__(self, device=None, debug_mode=False, src_path=None):
        super(Detector_WS, self).__init__(device, debug_mode, src_path)
        self.ws = None
        self.connect()
        self.uri = os.environ["MASK2FORMER_WS_URI"]

    def connect(self):
        try:
            self.ws = websocket.WebSocket(sslopt={"cert_reqs":ssl.CERT_NONE})
            self.ws.connect(self.uri, **self.proxy_config)
            print("Connected to", self.uri)
        except websocket.WebSocketConnectionClosedException as e:
            print("Failed to connect:", e)
            raise ConnectionError("Could not connect to WebSocket.") from e

    def model_inference(self, image: np.ndarray, road_mask: np.ndarray = None) -> np.ndarray:
        '''
        param: 
            image: RGB
        return:
            probs: np.ndarray (65, h, w)
        '''
        try:
            image = PIL.Image.fromarray(image)
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=50)
            self.ws.send(buffer.getvalue(), opcode=websocket.ABNF.OPCODE_BINARY)

            if road_mask is not None:
                buffer = io.BytesIO()
                np.savez_compressed(buffer, road_mask=road_mask)
                self.ws.send(buffer.getvalue(), opcode=websocket.ABNF.OPCODE_BINARY)
            else:
                buffer = io.BytesIO()
                np.savez_compressed(buffer, place_holder=0)
                self.ws.send(buffer.getvalue(), opcode=websocket.ABNF.OPCODE_BINARY)
            response = self.ws.recv()
            buffer = io.BytesIO(response)
            response = np.load(buffer)
            mask, conf = response['mask'], response['conf']
            conf = conf.astype(np.float32) / 255.0
            return mask, conf
        except websocket.WebSocketConnectionClosedException as e:
            # Optionally, try to reconnect and retry once
            self.connect()
            return self.model_inference(image, road_mask)
        except BrokenPipeError as e:
            # Optionally, try to reconnect and retry once
            self.connect()
            return self.model_inference(image, road_mask)
        except Exception as e:
            print("Semantic Segmentation Exception:", e)
            raise e
