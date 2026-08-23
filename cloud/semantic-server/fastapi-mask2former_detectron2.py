import numpy as np
import torch
import asyncio
import os, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Body, File, HTTPException, UploadFile, Response
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

torch.set_float32_matmul_precision(Config.float32_matmul_precision)

_Executor = ThreadPoolExecutor(max_workers=Config.num_thread)


def _quantize_uint8(tensor: torch.Tensor) -> np.ndarray:
    """Quantize on device, then copy back the uint8 result only.

    Equivalent to the host-side ``(value * 255).astype(np.uint8)``: both truncate
    toward zero after the same float32 multiply.
    """
    return (tensor * 255).to(torch.uint8).cpu().numpy()
    
                 
class MultiScalePredictor(DefaultPredictor):
    def __init__(self, cfg, with_crf=False, use_cuda_graph=False):
        super().__init__(cfg)
        self.with_crf = with_crf
        self.use_cuda_graph = use_cuda_graph
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
        return self.predict_batch([original_image])[0]

    def _get_or_capture_graph(self, inputs, short_edge, flip):
        """Get cached graph or capture a new one for this exact input shape.
        
        CUDA graphs require static shapes, so we key by (scale, actual_shape, flip, batch_size).
        """
        if not hasattr(self, '_cuda_graphs'):
            self._cuda_graphs = {}
        
        first_shape = tuple(inputs[0]["image"].shape)
        batch_size = len(inputs)
        key = (short_edge, first_shape, flip, batch_size)
        
        if key in self._cuda_graphs:
            return self._cuda_graphs[key]
        
        # Build static tensors
        static_tensors = []
        static_inputs = []
        for inp in inputs:
            tensor = torch.empty_like(inp["image"])
            static_tensors.append(tensor)
            static_inputs.append({"image": tensor, "height": inp["height"], "width": inp["width"]})
        
        # Warm-up
        for _ in range(3):
            for static_tensor, inp in zip(static_tensors, inputs):
                static_tensor.copy_(inp["image"])
            _ = self.model(static_inputs)
        torch.cuda.synchronize(self.cfg.MODEL.DEVICE)
        
        # Capture
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, stream=torch.cuda.Stream(self.cfg.MODEL.DEVICE)):
            static_outputs = self.model(static_inputs)
        
        graph_data = {
            'graph': graph,
            'static_tensors': static_tensors,
            'static_outputs': static_outputs,
        }
        self._cuda_graphs[key] = graph_data
        return graph_data

    def predict_batch(self, original_images):
        """Run the TTA sweep for several images in one pass per scale.

        Each scale issues about 1,700 kernel launches regardless of how many images
        it carries, so folding concurrent requests into one batch amortizes the
        launch cost that dominates this model on an H100.

        Args:
            original_images (list[np.ndarray]): images of shape (H, W, C) in BGR order.

        Returns:
            list[torch.Tensor]: the merged probability map per input image.
        """
        with torch.no_grad():  # https://github.com/sphinx-doc/sphinx/issues/4258
            # Apply pre-processing to image.
            images = []
            for original_image in original_images:
                rgb_original_image = original_image[:, :, ::-1]
                if self.input_format == "RGB":
                    # whether the model expects BGR inputs or RGB
                    original_image = rgb_original_image
                images.append(original_image)
            sizes = [image.shape[:2] for image in images]
            
            tta = self.cfg.TEST.AUG.ENABLED
            flip = self.cfg.TEST.AUG.FLIP
            short_edges = self.cfg.TEST.AUG.MIN_SIZES if tta else [self.cfg.INPUT.MIN_SIZE_TEST]
            max_edge = self.cfg.TEST.AUG.MAX_SIZE if tta else self.cfg.INPUT.MAX_SIZE_TEST

            views_per_image = 2 if (tta and flip) else 1
            predictions = [list() for _ in images]
            for short_edge in short_edges:
                aug = T.ResizeShortestEdge(
                    [short_edge, short_edge], max_edge
                )
                inputs = list()
                for original_image, (height, width) in zip(images, sizes):
                    image = aug.get_transform(original_image).apply_image(original_image).astype("float32").transpose(2, 0, 1)
                    image = torch.as_tensor(image, device=self.cfg.MODEL.DEVICE)
                    inputs.append({"image": image, "height": height, "width": width})
                    if views_per_image == 2:
                        inputs.append({"image": torch.flip(image, dims=[2]), "height": height, "width": width})

                if self.use_cuda_graph:
                    graph_data = self._get_or_capture_graph(inputs, short_edge, tta and flip)
                    for inp, static_tensor in zip(inputs, graph_data['static_tensors']):
                        static_tensor.copy_(inp["image"])
                    graph_data['graph'].replay()
                    results = [{"sem_seg": out["sem_seg"].clone()} for out in graph_data['static_outputs']]
                else:
                    results = self.model(inputs)
                for index in range(len(images)):
                    base = index * views_per_image
                    predictions[index].append(results[base]['sem_seg'])
                    if views_per_image == 2:
                        assert len(results[base + 1]['sem_seg'].shape) == 3
                        predictions[index].append(torch.flip(results[base + 1]['sem_seg'], dims=[2]))
            
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
            merged = [torch.stack(views, dim=0).mean(dim=0) for views in predictions]
            
            if self.with_crf:
                # 1/4 resolution
                # crf_image = torch.nn.functional.interpolate(crf_image, scale_factor=0.25, mode='bilinear', align_corners=False)
                # probs = torch.nn.functional.interpolate(probs, scale_factor=0.25, mode='bilinear', align_corners=False)
                merged = [self.crf(probs, image[:, :, ::-1]) for probs, image in zip(merged, images)]
                # height, width = rgb_original_image.shape[:2]
                # probs = torch.nn.functional.interpolate(probs.unsqueeze(0), size=(height, width), mode='bilinear', align_corners=False).squeeze(0)
            
            return merged

class Mask2Former:
    def __init__(self, device='cpu', config_file=None, use_cuda_graph=False) -> None:
        cfg = get_cfg()
        add_deeplab_config(cfg)
        add_maskformer2_config(cfg)

        cfg.merge_from_file(config_file)
        cfg.MODEL.DEVICE = device
        self.predictor = MultiScalePredictor(cfg, with_crf=False, use_cuda_graph=use_cuda_graph)
        self.device = device
        self.use_cuda_graph = use_cuda_graph
        
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
    
    def _finalize(self, probs, road_mask, return_probs):
        """Turn one probability map into the arrays its response carries.

        The reduction and the uint8 quantization run on the GPU, so the D2H copy is
        the response payload itself instead of the full 65x480x640 float32 volume.
        """
        # class_queries_logits = outputs.class_queries_logits
        # masks_queries_logits = outputs.masks_queries_logits
        # you can pass them to processor for postprocessing
        if return_probs:
            return _quantize_uint8(probs)
        if road_mask is not None:
            if isinstance(road_mask, np.ndarray):
                road_mask = torch.from_numpy(road_mask)
            mask, conf = self._post_process_road_mask(probs, road_mask.to(self.device))
        else:
            mask = torch.argmax(probs, dim=0)
            conf = probs.amax(dim=0)
        return mask.to(torch.uint8).cpu().numpy(), _quantize_uint8(conf)

    @torch.no_grad()
    def predict_batch(self, images: List[PIL.Image.Image], road_masks: list = None,
                      return_probs_flags: list = None) -> list:
        """Run one batched inference pass and finalize each request separately.

        Only the model pass is shared. Road-mask weighting and the choice between
        mask/confidence and quantized probabilities stay per request, so requests
        with different options can share a batch.
        """
        if road_masks is None:
            road_masks = [None] * len(images)
        if return_probs_flags is None:
            return_probs_flags = [False] * len(images)
        inputs = [np.array(image.convert("RGB"))[..., ::-1] for image in images]
        probs_batch = self.predictor.predict_batch(inputs)
        return [
            self._finalize(probs, road_mask, return_probs)
            for probs, road_mask, return_probs in zip(probs_batch, road_masks, return_probs_flags)
        ]

    def __call__(self, image: PIL.Image.Image, road_mask: Union[np.ndarray, torch.Tensor] = None,
                 return_probs: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        return self.predict_batch([image], [road_mask], [return_probs])[0]


_Resources = Queue()
for _ in range(Config.num_thread):
    _Resources.put((torch.cuda.Stream(), Mask2Former(Config.device, Config.config_file, Config.use_cuda_graph)))

def set_thread_number(num):
    global _Executor, _Resources
    _Executor = ThreadPoolExecutor(num)
    global _Resources
    while _Resources.qsize() < num:
        _Resources.put((torch.cuda.Stream(), Mask2Former(Config.device, Config.config_file)))

def batch_call(items: List[Tuple]) -> list:
    """Run one batched inference pass for a list of (image, road_mask, return_probs)."""
    global _Resources
    cuda_stream, model = _Resources.get()
    try:
        with torch.cuda.stream(cuda_stream):
            start_time = time.time()
            results = model.predict_batch(
                [item[0] for item in items],
                [item[1] for item in items],
                [item[2] for item in items],
            )
            elapsed = time.time() - start_time
            logger.info(f"Time elapsed: {elapsed} for batch of {len(items)} ({elapsed / len(items)} per request)")
    except Exception as e:
        _Resources.put((cuda_stream, model))
        logger.error("Execution Error: {} \nDetailed Trace:\n{}".format(str(e), format_error(e)))
        raise e
    _Resources.put((cuda_stream, model))
    return results


def thread_call(image: Union[PIL.Image.Image, np.ndarray], road_mask: np.ndarray = None,
                return_probs: bool = False) -> np.ndarray:
    return batch_call([(image, road_mask, return_probs)])[0]


class QueueFull(Exception):
    """Raised when the bounded request queue is saturated."""


class BatchScheduler:
    """Folds concurrent requests into one GPU batch behind a bounded queue.

    A single worker thread owns the model, so requests were already serialized. The
    scheduler takes whatever has piled up while the previous batch was running, which
    forms batches under load without adding any wait at low load. max_wait_seconds
    above zero additionally lingers for late arrivals.
    """

    _POLL_SECONDS = 0.001

    def __init__(self, max_batch_size: int, max_wait_seconds: float, max_queue_size: int):
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_wait_seconds = max(0.0, float(max_wait_seconds))
        self.max_queue_size = max(0, int(max_queue_size))
        self._queue = None
        self._worker = None

    def _ensure_started(self):
        if self._worker is None or self._worker.done():
            self._queue = asyncio.Queue()
            self._worker = asyncio.get_running_loop().create_task(self._run())

    async def submit(self, image, road_mask=None, return_probs=False):
        self._ensure_started()
        if self.max_queue_size and self._queue.qsize() >= self.max_queue_size:
            raise QueueFull(f"request queue is full ({self.max_queue_size})")
        future = asyncio.get_running_loop().create_future()
        self._queue.put_nowait((image, road_mask, return_probs, future))
        return await future

    async def _collect(self):
        batch = [await self._queue.get()]
        if self.max_batch_size == 1:
            return batch
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.max_wait_seconds
        while len(batch) < self.max_batch_size:
            try:
                batch.append(self._queue.get_nowait())
                continue
            except asyncio.QueueEmpty:
                pass
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(remaining, self._POLL_SECONDS))
        return batch

    async def _run(self):
        loop = asyncio.get_running_loop()
        while True:
            batch = await self._collect()
            try:
                results = await loop.run_in_executor(_Executor, batch_call, [item[:3] for item in batch])
            except Exception as error:
                for item in batch:
                    if not item[3].done():
                        item[3].set_exception(error)
                continue
            for item, result in zip(batch, results):
                if not item[3].done():
                    item[3].set_result(result)


_Scheduler = BatchScheduler(Config.max_batch_size, Config.max_batch_wait_ms / 1000.0, Config.max_queue_size)

app = FastAPI()


async def _submit(image, road_mask=None, return_probs=False):
    """Enqueue one request, answering 503 rather than queueing without bound."""
    try:
        return await _Scheduler.submit(image, road_mask, return_probs)
    except QueueFull as error:
        raise HTTPException(status_code=503, detail=str(error))

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
    buffer = io.BytesIO()
    if return_probs:
        probs = await _submit(image, None, True)
        print("model inference:", time.time() - last_time)
        last_time = time.time()
        np.savez_compressed(buffer, probs)
        print("probs compress:", time.time() - last_time)
        last_time = time.time()
    else:
        if road_mask is not None:
            compressed_data = await road_mask.read()
            print("road mask read:", time.time() - last_time)
            last_time = time.time()
            road_mask = np.load(io.BytesIO(compressed_data))['arr_0']
            print("road mask decode:", time.time() - last_time)
            last_time = time.time()
        mask, conf = await _submit(image, road_mask)
        print("model inference:", time.time() - last_time)
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
    await _submit(image)
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
                probs = await _Scheduler.submit(image, None, True)
                np.savez_compressed(buffer, probs=probs)
            else:
                road_mask = None
                if 'road_mask' in npdata and npdata['road_mask'].shape == image.size[::-1]:
                    road_mask = npdata['road_mask']
                mask, conf = await _Scheduler.submit(image, road_mask)
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

