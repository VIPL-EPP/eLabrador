import numpy as np
import torch
import asyncio
import os, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Body, File, UploadFile, Response
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import io
from config import Mask2FormerDetectron2Config as Config
import logging
from utils import format_error
import PIL.Image
from typing import Union, Optional, List, Tuple
import json
from utils import generate_temp_filepath

import detectron2
import detectron2.data.transforms as T
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.projects.deeplab import add_deeplab_config
# import Mask2Former project
from mask2former import add_maskformer2_config


logger = logging.getLogger("mask2former_detectron2")
logger.setLevel(level = logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
if os.getenv("NVI_LOG_DIR") is not None:
    os.makedirs(os.getenv("NVI_LOG_DIR"), exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(os.getenv("NVI_LOG_DIR"), logger.name+".log"))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

_Executor = ThreadPoolExecutor(max_workers=Config.num_thread)
    
                 
class MultiScalePredictor(DefaultPredictor):
    def __init__(self, cfg, with_crf=False):
        super().__init__(cfg)
        self.with_crf = with_crf
        assert not with_crf, "CRF is not supported yet"
    
    def __call__(self, original_image):
        """
        Args:
            original_image (np.ndarray): an image of shape (H, W, C) (in BGR order).

        Returns:
            predictions (dict):
                the output of the model for one image only.
                See :doc:`/tutorials/models` for details about the format.
        """
        with torch.no_grad():  # https://github.com/sphinx-doc/sphinx/issues/4258
            # Apply pre-processing to image.
            rgb_original_image = original_image[:, :, ::-1]
            if self.input_format == "RGB":
                # whether the model expects BGR inputs or RGB
                original_image = rgb_original_image
            height, width = original_image.shape[:2]
            
            tta = self.cfg.TEST.AUG.ENABLED
            flip = self.cfg.TEST.AUG.FLIP
            short_edges = self.cfg.TEST.AUG.MIN_SIZES if tta else [self.cfg.INPUT.MIN_SIZE_TEST]
            max_edge = self.cfg.TEST.AUG.MAX_SIZE if tta else self.cfg.INPUT.MAX_SIZE_TEST

            print("short edges:", short_edges)
            
            predictions = list()
            for short_edge in short_edges:
                aug = T.ResizeShortestEdge(
                    [short_edge, short_edge], max_edge
                )
                image = aug.get_transform(original_image).apply_image(original_image).astype("float32").transpose(2, 0, 1)
                image = torch.as_tensor(image, device=self.cfg.MODEL.DEVICE)

                inputs = [{"image": image, "height": height, "width": width}]

                if tta and flip:
                    image_f = torch.flip(image, dims=[2])
                    inputs.append({"image": image_f, "height": height, "width": width})
                    results = self.model(inputs)
                    assert len(results[-1]['sem_seg'].shape) == 3
                    results[-1]['sem_seg'] = torch.flip(results[-1]['sem_seg'], dims=[2])
                else:
                    results = self.model(inputs)

                predictions.extend(results)
            
            # inputs = list()
            # for short_edge in short_edges:
            #     aug = T.ResizeShortestEdge(
            #         [short_edge, short_edge], max_edge
            #     )
            #     image = aug.get_transform(original_image).apply_image(original_image).astype("float32").transpose(2, 0, 1)
            #     image = torch.as_tensor(image, device=self.cfg.MODEL.DEVICE)

            #     inputs.append({"image": image, "height": height, "width": width})

            #     if tta and flip:
            #         image_f = torch.flip(image, dims=[2])
            #         inputs.append({"image": image_f, "height": height, "width": width})
            
            # predictions = self.model(inputs)
            # if tta and flip:
            #     for i in range(1, len(predictions), 2):
            #         assert len(predictions[i]['sem_seg'].shape) == 3
            #         predictions[i]['sem_seg'] = torch.flip(predictions[i]['sem_seg'], dims=[2])
                    
            # voting merge
            # probs = torch.zeros_like(predictions[0]['sem_seg'], dtype=torch.float)
            # for i in range(len(predictions)):
            #     prob = predictions[i]['sem_seg']
            #     max_v = torch.max(predictions[i]['sem_seg'], dim=0).values
            #     probs[prob == max_v.unsqueeze(0)] += 1
            # probs = probs / len(predictions)
            
            # average merge
            probs = torch.stack([p['sem_seg'] for p in predictions], dim=0).mean(dim=0)
            
            if self.with_crf:
                # 1/4 resolution
                # crf_image = torch.nn.functional.interpolate(crf_image, scale_factor=0.25, mode='bilinear', align_corners=False)
                # probs = torch.nn.functional.interpolate(probs, scale_factor=0.25, mode='bilinear', align_corners=False)
                probs = self.crf(probs, rgb_original_image)
                # height, width = rgb_original_image.shape[:2]
                # probs = torch.nn.functional.interpolate(probs.unsqueeze(0), size=(height, width), mode='bilinear', align_corners=False).squeeze(0)
            
            return probs

class Mask2Former:
    def __init__(self, device='cpu', config_file=None) -> None:
        cfg = get_cfg()
        add_deeplab_config(cfg)
        add_maskformer2_config(cfg)

        cfg.merge_from_file(config_file)
        cfg.MODEL.DEVICE = device
        self.predictor = MultiScalePredictor(cfg, with_crf=False)
        self.device = device
        
        self.dataset_meta = json.load(open("configs/mapillary_dataconfig.json", "r"))
        self.categories = self.dataset_meta["labels"][:-1]
        self.road_available_categories_mask = np.array([c["available_on_ground"] for c in self.categories], dtype=np.bool_)
        # self.road_determine_categories_mask = np.array(["construction--flat" in self.categories[c]["name"] or "marking--" in self.categories[c]["name"] for c in range(len(self.categories))], dtype=np.bool_)
        walkable_idx = list()
        for cid in range(len(self.categories)):
            if "pedestrian-area" in self.categories[cid]['name']:
                walkable_idx.append(cid)
                self.pedestrain_area_idx = cid
            elif "sidewalk" in self.categories[cid]['name']:
                walkable_idx.append(cid)
                self.sidewalk_idx = cid
            elif "crosswalk-zebra" in self.categories[cid]['name']:
                walkable_idx.append(cid)
        self.road_available_categories_mask = torch.from_numpy(self.road_available_categories_mask).to(self.device)

    def _post_process_road_mask(self, probs, road_mask):
        probs[:, road_mask] *= self.road_available_categories_mask.reshape(-1, 1)
        probs[self.sidewalk_idx, road_mask] += probs[self.pedestrain_area_idx, road_mask]
        conf, mask = torch.max(probs, dim=0)
        return mask, conf
    
    @torch.no_grad()
    def __call__(self, image: PIL.Image.Image, road_mask: Union[np.ndarray, torch.Tensor] = None) -> np.ndarray:
        if road_mask is not None:
            if isinstance(road_mask, np.ndarray):
                road_mask = torch.from_numpy(road_mask)
            road_mask = road_mask.to(self.device)
        inputs = np.array(image.convert("RGB"))[..., ::-1]
        probs = self.predictor(inputs)
        
        # class_queries_logits = outputs.class_queries_logits
        # masks_queries_logits = outputs.masks_queries_logits
        # you can pass them to processor for postprocessing
        if road_mask is not None:
            mask, conf = self._post_process_road_mask(probs, road_mask)
            return mask.cpu().numpy().astype(np.uint8), conf.cpu().numpy().astype(np.float32)
        else:
            mask = torch.argmax(probs, dim=0)
            return mask.cpu().numpy().astype(np.uint8), probs.cpu().numpy().astype(np.float32)


_Resources = Queue()
for _ in range(Config.num_thread):
    _Resources.put((torch.cuda.Stream(), Mask2Former(Config.device, Config.config_file)))

def set_thread_number(num):
    global _Executor, _Resources
    _Executor = ThreadPoolExecutor(num)
    global _Resources
    while _Resources.qsize() < num:
        _Resources.put((torch.cuda.Stream(), Mask2Former(Config.device, Config.config_file)))

def thread_call(image: Union[PIL.Image.Image, np.ndarray], road_mask: np.ndarray = None) -> np.ndarray:
    global _Resources
    cuda_stream, model = _Resources.get()
    try:
        with torch.cuda.stream(cuda_stream):
            import time
            start_time = time.time()
            result = model(image, road_mask)
            end_time = time.time()
            logger.info(f"Time elapsed: {end_time - start_time}")
    except Exception as e:
        _Resources.put((cuda_stream, model))
        logger.error("Execution Error: {} \nDetailed Trace:\n{}".format(str(e), format_error(e)))
        raise e
    _Resources.put((cuda_stream, model))
    return result

app = FastAPI()

@app.post("/predict")
async def predict(image: UploadFile = File(...), road_mask: UploadFile = File(default=None), return_probs: bool = Body(False)):
    last_time = start_time = time.time()
    print("--------------------")
    compressed_data = await image.read()
    print("data read:", time.time() - last_time, len(compressed_data)/1024, "KB")
    last_time = time.time()
    buffer = io.BytesIO(compressed_data)
    image = PIL.Image.open(buffer)
    print("image decode:", time.time() - last_time)
    last_time = time.time()
    loop = asyncio.get_running_loop()
    if road_mask is None:
        sem_seg, probs = await loop.run_in_executor(_Executor, thread_call, image)
        print("model inference:", time.time() - last_time)
        last_time = time.time()
    elif return_probs:
        sem_seg, probs = await loop.run_in_executor(_Executor, thread_call, image)
        print("model inference:", time.time() - last_time)
        last_time = time.time()
    buffer = io.BytesIO()
    if return_probs:
        probs = (probs*255).astype(np.uint8)
        np.savez_compressed(buffer, probs)
        print("probs compress:", time.time() - last_time)
        last_time = time.time()
    else:
        if road_mask is not None:
            compressed_data = await road_mask.read()
            print("road mask read:", time.time() - last_time)
            last_time = time.time()
            buffer = io.BytesIO(compressed_data)
            road_mask = np.load(buffer)['arr_0']
            print("road mask decode:", time.time() - last_time)
            last_time = time.time()
            mask, conf = await loop.run_in_executor(_Executor, thread_call, image, road_mask)
            print("model inference:", time.time() - last_time)
            last_time = time.time()
        else:
            mask = sem_seg
            conf = np.max(probs, axis=0)
        conf = (conf*255).astype(np.uint8)
        print("retval prepare:", time.time() - last_time)
        last_time = time.time()
        np.savez_compressed(buffer, mask=mask, conf=conf)
        print("retval compress:", time.time() - last_time)
        last_time = time.time()
    print("Total:",  time.time() - start_time, "Bytes:", len(buffer.getvalue())/1024, "KB")
    return Response(content=buffer.getvalue(), media_type="application/octet-stream")


@app.post("/predict_minimize")
async def predict(image: UploadFile = File(...)):
    last_time = start_time = time.time()
    print("--------------------")
    compressed_data = await image.read()
    print("data read:", time.time() - last_time)
    last_time = time.time()
    buffer = io.BytesIO(compressed_data)
    image = PIL.Image.open(buffer)
    print("image decode:", time.time() - last_time)
    last_time = time.time()
    loop = asyncio.get_running_loop()
    sem_seg, probs = await loop.run_in_executor(_Executor, thread_call, image)
    print("model inference:", time.time() - last_time)
    last_time = time.time()
    print("Total:",  time.time() - start_time, "Bytes:", len(buffer.getvalue()))
    return Response(content=compressed_data, media_type="application/octet-stream")


# @app.post("/predict_delta")
# async def predict(image: UploadFile = File(...), return_probs: bool = Body(False), last_filename: str = Body("")):
#     compressed_data = await image.read()
#     delta_image = np.array(PIL.Image.open(io.BytesIO(compressed_data)).convert("RGB"))
#     if len(last_filename)>0 and os.path.exists(last_filename):
#         last_image = np.array(PIL.Image.open(last_filename).convert("RGB"))
#         image = delta_image + last_image
#     else:
#         image = delta_image
#     buffer = await _predict(image, return_probs)
#     return Response(content=buffer.getvalue(), media_type="application/octet-stream")


@app.websocket("/predict_ws")
async def predict_ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            data = await websocket.receive_bytes()
            # TODO: check if helpful
            buffer = io.BytesIO(data)
            image = PIL.Image.open(buffer)
            data = await websocket.receive_bytes()
            buffer = io.BytesIO(data)
            npdata = np.load(buffer)

            buffer = io.BytesIO()
            if 'return_probs' in npdata and npdata['return_probs']:
                sem_seg, probs = await asyncio.get_event_loop().run_in_executor(_Executor, thread_call, image)
                probs = (probs * 255).astype(np.uint8)
                np.savez_compressed(buffer, probs=probs)
            elif 'road_mask' in npdata and npdata['road_mask'].shape == image.size[::-1]:
                road_mask = npdata['road_mask']
                mask, conf = await asyncio.get_event_loop().run_in_executor(_Executor, thread_call, image, road_mask)
                conf = (conf * 255).astype(np.uint8)
                np.savez_compressed(buffer, mask=mask, conf=conf)
            else:
                sem_seg, probs = await asyncio.get_event_loop().run_in_executor(_Executor, thread_call, image)
                mask = sem_seg
                conf = np.max(probs, axis=0)
                conf = (conf * 255).astype(np.uint8)
                np.savez_compressed(buffer, mask=mask, conf=conf)
            await websocket.send_bytes(buffer.getvalue())
        except WebSocketDisconnect:
            break
        except Exception as e:
            logger.error("Execution Error: {} \nDetailed Trace:\n{}".format(str(e), format_error(e)))
            await websocket.close()
            pass
    return

# @app.post("/predict")
# def predict(image: UploadFile = File(...)):
#     print("get in predict")
#     compressed_data = image.file.read()
#     print("read data")
#     image = np.load(io.BytesIO(compressed_data))['arr_0']
#     print("np.load")
#     result = thread_call(image) # thread_call(image)
#     buffer = io.BytesIO()
#     np.savez_compressed(buffer, np.array(result))
#     return Response(content=buffer.getvalue(), media_type="application/octet-stream")

