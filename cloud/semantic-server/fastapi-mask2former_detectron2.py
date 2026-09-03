import numpy as np
import torch
import asyncio
import os, time
import itertools
from contextlib import contextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Body, File, HTTPException, UploadFile, Response
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue
import io
from batch_scheduler import BatchQueue, QueueFull
from config import Mask2FormerDetectron2Config as Config
import logging
from npz_codec import encode_npz_async
from utils import format_error
import PIL.Image
from typing import Union, Optional, List, Tuple, NamedTuple
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

_AUTOCAST_DTYPES = {
    'none': None,
    'bfloat16': torch.bfloat16,
    'float16': torch.float16,
}
if Config.autocast_dtype not in _AUTOCAST_DTYPES:
    raise ValueError("NVI_AUTOCAST_DTYPE must be one of: none, bfloat16, float16")
if Config.msdeform_impl not in (
    'legacy', 'h100-fixed-fp32', 'bw1000-fixed-fp32'
):
    raise ValueError(
        "NVI_MSDEFORM_IMPL must be one of: legacy, h100-fixed-fp32, "
        "bw1000-fixed-fp32"
    )
if Config.msdeform_norm_impl not in ('legacy', 'compiled'):
    raise ValueError(
        "NVI_MSDEFORM_NORM_IMPL must be one of: legacy, compiled"
    )
if Config.msdeform_ffn_impl not in ('legacy', 'compiled-bf16'):
    raise ValueError(
        "NVI_MSDEFORM_FFN_IMPL must be one of: legacy, compiled-bf16"
    )
if Config.upsample_pointwise_impl not in ('legacy', 'compiled'):
    raise ValueError(
        "NVI_UPSAMPLE_POINTWISE_IMPL must be one of: legacy, compiled"
    )
if Config.semantic_batch_impl not in ('legacy', 'batched', 'compiled-batched'):
    raise ValueError(
        "NVI_SEMANTIC_BATCH_IMPL must be one of: legacy, batched, compiled-batched"
    )
if Config.batch_policy not in BatchQueue.POLICIES:
    raise ValueError(
        "NVI_BATCH_POLICY must be one of: adaptive, fixed, opportunistic, pipeline"
    )
if Config.max_batch_wait_ms < 0:
    raise ValueError("NVI_MAX_BATCH_WAIT_MS must be non-negative")
if Config.cuda_graph_max_batch_size < 1:
    raise ValueError("NVI_CUDA_GRAPH_MAX_BATCH_SIZE must be at least 1")
if Config.batch_max_queue_delay_ms < 0:
    raise ValueError("NVI_BATCH_MAX_QUEUE_DELAY_MS must be non-negative")
if Config.batch_adaptive_min_batch_size < 1:
    raise ValueError("NVI_BATCH_ADAPTIVE_MIN_BATCH_SIZE must be at least 1")
if Config.batch_adaptive_max_misses < 1:
    raise ValueError("NVI_BATCH_ADAPTIVE_MAX_MISSES must be at least 1")
if Config.batch_adaptive_cooldown_ms < 0:
    raise ValueError("NVI_BATCH_ADAPTIVE_COOLDOWN_MS must be non-negative")
logger.info(
    "precision configuration: float32_matmul_precision=%s autocast_dtype=%s "
    "swin_attention_impl=%s swin_ffn_impl=%s decoder_pointwise_impl=%s "
    "msdeform_impl=%s msdeform_norm_impl=%s msdeform_ffn_impl=%s "
    "upsample_pointwise_impl=%s "
    "semantic_batch_impl=%s cuda_graph=%s cuda_graph_max_batch_size=%s",
    Config.float32_matmul_precision,
    Config.autocast_dtype,
    Config.swin_attention_impl,
    Config.swin_ffn_impl,
    Config.decoder_pointwise_impl,
    Config.msdeform_impl,
    Config.msdeform_norm_impl,
    Config.msdeform_ffn_impl,
    Config.upsample_pointwise_impl,
    Config.semantic_batch_impl,
    Config.use_cuda_graph,
    Config.cuda_graph_max_batch_size,
)
if Config.compress_threads < 1:
    raise ValueError("NVI_COMPRESS_THREADS must be at least 1")
if not 0 <= Config.npz_compression_level <= 9:
    raise ValueError("NVI_NPZ_COMPRESSION_LEVEL must be between 0 and 9")
logger.info(
    "response compression: npz_deflate_level=%s threads=%s",
    Config.npz_compression_level,
    Config.compress_threads,
)
logger.info("scheduler profile timing: %s", Config.profile_scheduler_timing)
logger.info(
    "batch scheduler: policy=%s max_batch=%s max_wait_ms=%s "
    "max_queue_delay_ms=%s min_wait_batch=%s max_misses=%s "
    "cooldown_ms=%s max_queue=%s",
    Config.batch_policy,
    Config.max_batch_size,
    Config.max_batch_wait_ms,
    Config.batch_max_queue_delay_ms,
    Config.batch_adaptive_min_batch_size,
    Config.batch_adaptive_max_misses,
    Config.batch_adaptive_cooldown_ms,
    Config.max_queue_size,
)


@contextmanager
def _profile_nvtx(label):
    """Emit stable NVTX ranges only for the opt-in profiling path."""
    if not Config.profile_scheduler_timing:
        yield
        return
    torch.cuda.nvtx.range_push(label)
    try:
        yield
    finally:
        torch.cuda.nvtx.range_pop()

_Executor = ThreadPoolExecutor(max_workers=Config.num_thread)
# Decode and resize hold no model state, so they run on their own threads instead of
# the single inference thread. Off the inference thread, the fixed production resize
# overlaps the GPU work of an earlier batch and several requests can run it at once.
_PreprocExecutor = ThreadPoolExecutor(max_workers=Config.preproc_threads,
                                      thread_name_prefix="preproc")
_CompressExecutor = ThreadPoolExecutor(max_workers=Config.compress_threads,
                                       thread_name_prefix="npz-compress")


async def _encode_npz_response(arrays) -> bytes:
    """Encode one response off the event loop on the dedicated compression pool."""
    return await encode_npz_async(
        arrays,
        compression_level=Config.npz_compression_level,
        executor=_CompressExecutor,
    )


class PreparedImage(NamedTuple):
    """One request's model inputs: a CHW float32 array per TTA scale.

    Entries may be futures. The TTA loop consumes the scales in order and spends
    about 17 ms of GPU time on each, so only the first scale gates the start of the
    forward pass; the rest finish on the preprocessing pool during it.
    """
    views: list
    height: int
    width: int

    def view(self, index):
        """The array for one scale, waiting for it if the resize is still running."""
        entry = self.views[index]
        return entry.result() if isinstance(entry, Future) else entry

    async def wait_until_model_ready(self):
        """Wait outside the model worker for the first (production-only) view."""
        entry = self.views[0]
        if isinstance(entry, Future):
            await asyncio.wrap_future(entry)
        return self


def _parse_shapes(text):
    """Input sizes to capture graphs for, given as a comma separated list of WxH."""
    shapes = list()
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        width, _, height = item.partition("x")
        shapes.append((int(width), int(height)))
    return shapes


def _tta_scales(cfg):
    """Return the single production input geometry (768px short, 1024px long).

    Camera frames are 640x480 (4:3), so Detectron2's shortest-edge resize yields
    exactly 1024x768 while preserving aspect ratio.  TTA is intentionally ignored.
    """
    return [768], 1024


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
        self.autocast_dtype = _AUTOCAST_DTYPES[Config.autocast_dtype]
        self.preprocessor = ImagePreprocessor(self.cfg)
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
        return self.predict_batch([self.preprocessor(original_image)])[0]

    def _get_or_capture_graph(self, inputs, short_edge, flip):
        """Get cached graph or capture a new one for this exact input shape.
        
        CUDA graphs require static tensor shapes and static Detectron2 output sizes.
        Keep every request's shape/height/width in the key; batch size is implicit in
        the signature length.
        """
        if not hasattr(self, '_cuda_graphs'):
            self._cuda_graphs = {}
        
        input_signature = tuple(
            (tuple(inp["image"].shape), int(inp["height"]), int(inp["width"]))
            for inp in inputs
        )
        key = (short_edge, input_signature, flip)
        
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

    def release_cuda_graphs(self):
        """Release graph executables and their private pools before process exit."""
        graphs = getattr(self, '_cuda_graphs', {})
        for graph_data in graphs.values():
            graph_data['graph'].reset()
        graphs.clear()
        torch.cuda.empty_cache()

    def predict_batch(self, prepared_images):
        """Run one fixed-size, non-TTA inference pass for a batch of images.

        Each scale issues about 1,700 kernel launches regardless of how many images
        it carries, so folding concurrent requests into one batch amortizes the
        launch cost that dominates this model on an H100.

        Args:
            prepared_images (list[PreparedImage]): output of :class:`ImagePreprocessor`.

        Returns:
            list[torch.Tensor]: the merged probability map per input image.
        """
        # Keep the autocast scope around both eager execution and graph capture.
        # Pixel decoder components that explicitly disable autocast remain FP32.
        # Autocast's weight cache is scoped to the context manager. A CUDA Graph
        # captured with cached low-precision weights can retain pointers after that
        # cache is released, and capturing another batch-size graph may then make the
        # earlier graph fault on replay. With graphs, capture the casts themselves so
        # every graph owns stable buffers in its private memory pool.
        use_cuda_graph = (
            self.use_cuda_graph
            and len(prepared_images) <= Config.cuda_graph_max_batch_size
        )
        autocast = (
            torch.autocast(
                'cuda',
                dtype=self.autocast_dtype,
                cache_enabled=not use_cuda_graph,
            )
            if self.autocast_dtype
            else torch.autocast('cuda', enabled=False)
        )
        with torch.no_grad(), autocast:  # https://github.com/sphinx-doc/sphinx/issues/4258
            short_edges, _ = _tta_scales(self.cfg)
            predictions = [list() for _ in prepared_images]
            for scale_index, short_edge in enumerate(short_edges):
                inputs = list()
                for prepared in prepared_images:
                    image = torch.as_tensor(prepared.view(scale_index), device=self.cfg.MODEL.DEVICE)
                    inputs.append({"image": image, "height": prepared.height, "width": prepared.width})
                if use_cuda_graph:
                    graph_data = self._get_or_capture_graph(inputs, short_edge, False)
                    for inp, static_tensor in zip(inputs, graph_data['static_tensors']):
                        static_tensor.copy_(inp["image"])
                    graph_data['graph'].replay()
                    results = [{"sem_seg": out["sem_seg"].clone()} for out in graph_data['static_outputs']]
                else:
                    results = self.model(inputs)
                for index in range(len(prepared_images)):
                    predictions[index].append(results[index]['sem_seg'])
            
            merged = [views[0] for views in predictions]
            
            if self.with_crf:
                # 1/4 resolution
                # crf_image = torch.nn.functional.interpolate(crf_image, scale_factor=0.25, mode='bilinear', align_corners=False)
                # probs = torch.nn.functional.interpolate(probs, scale_factor=0.25, mode='bilinear', align_corners=False)
                merged = [self.crf(probs, image[:, :, ::-1]) for probs, image in zip(merged, images)]
                # height, width = rgb_original_image.shape[:2]
                # probs = torch.nn.functional.interpolate(probs.unsqueeze(0), size=(height, width), mode='bilinear', align_corners=False).squeeze(0)
            
            return merged


def _build_cfg(device, config_file):
    """Assemble the detectron2 config the predictor and the preprocessor share."""
    cfg = get_cfg()
    add_deeplab_config(cfg)
    add_maskformer2_config(cfg)

    cfg.merge_from_file(config_file)
    cfg.MODEL.DEVICE = device
    return cfg


class ImagePreprocessor:
    """The CPU half of a request: JPEG decode and one resize per TTA scale.

    Holds no model state and no device state, so instances are safe to call from
    several threads at once. The resize call sequence matches what the predictor
    previously performed inline, so the arrays reaching the model are unchanged.
    """

    def __init__(self, cfg):
        self.input_format = cfg.INPUT.FORMAT
        assert self.input_format in ["RGB", "BGR"], self.input_format
        self.short_edges, self.max_edge = _tta_scales(cfg)

    def decode(self, image: Union[PIL.Image.Image, np.ndarray]) -> np.ndarray:
        """Decode the JPEG and put the channels in the order the model expects."""
        if isinstance(image, PIL.Image.Image):
            original_image = np.array(image.convert("RGB"))[..., ::-1]
        else:
            original_image = image
        rgb_original_image = original_image[:, :, ::-1]
        if self.input_format == "RGB":
            # whether the model expects BGR inputs or RGB
            original_image = rgb_original_image
        return original_image

    def resize(self, original_image: np.ndarray, index: int) -> np.ndarray:
        """Produce the CHW float32 array for one TTA scale."""
        aug = T.ResizeShortestEdge(
            [self.short_edges[index], self.short_edges[index]], self.max_edge
        )
        return aug.get_transform(original_image).apply_image(original_image).astype("float32").transpose(2, 0, 1)

    def fan_out(self, original_image: np.ndarray, executor) -> PreparedImage:
        """Submit one resize task per scale and return them as pending views."""
        height, width = original_image.shape[:2]
        views = [executor.submit(self.resize, original_image, index)
                 for index in range(len(self.short_edges))]
        return PreparedImage(views=views, height=height, width=width)

    def __call__(self, image: Union[PIL.Image.Image, np.ndarray]) -> PreparedImage:
        """Decode and resize every scale on the calling thread."""
        original_image = self.decode(image)
        height, width = original_image.shape[:2]
        views = [self.resize(original_image, index) for index in range(len(self.short_edges))]
        return PreparedImage(views=views, height=height, width=width)


class Mask2Former:
    def __init__(self, device='cpu', config_file=None, use_cuda_graph=False) -> None:
        cfg = _build_cfg(device, config_file)
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
    def predict_batch(self, prepared_images: List[PreparedImage], road_masks: list = None,
                      return_probs_flags: list = None, profile_timing: bool = False):
        """Run one batched inference pass and finalize each request separately.

        Takes the output of :class:`ImagePreprocessor`, so decode and resize have
        already happened on another thread. Only the model pass is shared. Road-mask
        weighting and the choice between mask/confidence and quantized probabilities
        stay per request. The service scheduler separates the two output modes to
        avoid head-of-line blocking, while different road masks may share a batch.
        """
        if road_masks is None:
            road_masks = [None] * len(prepared_images)
        if return_probs_flags is None:
            return_probs_flags = [False] * len(prepared_images)
        if profile_timing:
            gpu_start = torch.cuda.Event(enable_timing=True)
            forward_end = torch.cuda.Event(enable_timing=True)
            gpu_end = torch.cuda.Event(enable_timing=True)
            gpu_start.record()
        with _profile_nvtx(f"service_gpu_forward_batch_{len(prepared_images)}"):
            probs_batch = self.predictor.predict_batch(prepared_images)
        if profile_timing:
            forward_end.record()
        with _profile_nvtx(f"service_gpu_finalize_batch_{len(prepared_images)}"):
            results = [
                self._finalize(probs, road_mask, return_probs)
                for probs, road_mask, return_probs in zip(
                    probs_batch, road_masks, return_probs_flags
                )
            ]
        if not profile_timing:
            return results
        gpu_end.record()
        gpu_end.synchronize()
        forward_ms = float(gpu_start.elapsed_time(forward_end))
        total_ms = float(gpu_start.elapsed_time(gpu_end))
        return results, {
            "gpu_forward_ms": forward_ms,
            "gpu_finalize_ms": total_ms - forward_ms,
            "gpu_total_ms": total_ms,
        }

    def warmup(self, shapes, max_batch_size):
        """Capture the CUDA graphs for the declared input sizes before serving starts.

        A graph is keyed by scale, flip and every input's tensor/output signature. The first request
        carrying a key that has not been captured yet pays the capture cost inside its
        own latency; the measured value is 1.31 s against a 0.24 s steady state, and it
        appears as the p95 at concurrency 4 because the scheduler only produces the
        larger batch sizes once load arrives. Capturing here moves that cost to startup
        for the sizes listed. Sizes outside the list are still captured on first use.
        """
        if not self.use_cuda_graph:
            return
        for width, height in shapes:
            prepared = self.predictor.preprocessor(
                np.full((height, width, 3), 128, dtype=np.uint8))
            graph_batch_limit = min(
                max_batch_size, Config.cuda_graph_max_batch_size
            )
            for batch_size in range(1, graph_batch_limit + 1):
                started = time.time()
                self.predict_batch([prepared] * batch_size)
                print(f"graph capture {width}x{height} batch {batch_size}: "
                      f"{time.time() - started:.3f}s", flush=True)

    def __call__(self, image: PIL.Image.Image, road_mask: Union[np.ndarray, torch.Tensor] = None,
                 return_probs: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        return self.predict_batch([_Preprocessor(image)], [road_mask], [return_probs])[0]


_Preprocessor = ImagePreprocessor(_build_cfg(Config.device, Config.config_file))

_Resources = Queue()
_Models = []
for _ in range(Config.num_thread):
    _model = Mask2Former(Config.device, Config.config_file, Config.use_cuda_graph)
    _model.warmup(_parse_shapes(Config.warmup_shapes), Config.max_batch_size)
    _Models.append(_model)
    _Resources.put((torch.cuda.Stream(), _model))

def set_thread_number(num):
    """Grow the worker pool and add one model instance per new worker.

    The added instances are built with the same CUDA graph settings as the ones created
    at import time, so a worker added here behaves the same as the initial worker. Each
    instance holds its own graphs, so the resident memory scales with the worker count.
    """
    global _Executor, _Resources
    _Executor = ThreadPoolExecutor(num)
    while _Resources.qsize() < num:
        model = Mask2Former(Config.device, Config.config_file, Config.use_cuda_graph)
        model.warmup(_parse_shapes(Config.warmup_shapes), Config.max_batch_size)
        _Models.append(model)
        _Resources.put((torch.cuda.Stream(), model))

def batch_call(items: List[Tuple], profile_context=None):
    """Run one batched inference pass for a list of (prepared, road_mask, return_probs)."""
    global _Resources
    thread_started_ns = time.perf_counter_ns()
    resource_wait_started_ns = thread_started_ns
    cuda_stream, model = _Resources.get()
    resource_acquired_ns = time.perf_counter_ns()
    try:
        with torch.cuda.stream(cuda_stream):
            start_ns = time.perf_counter_ns()
            with _profile_nvtx(f"service_batch_{len(items)}"):
                batch_result = model.predict_batch(
                    [item[0] for item in items],
                    [item[1] for item in items],
                    [item[2] for item in items],
                    profile_timing=profile_context is not None,
                )
            end_ns = time.perf_counter_ns()
            if profile_context is None:
                results = batch_result
                gpu_timing = None
            else:
                results, gpu_timing = batch_result
            elapsed = (end_ns - start_ns) / 1e9
            logger.info(f"Time elapsed: {elapsed} for batch of {len(items)} ({elapsed / len(items)} per request)")
    except Exception as e:
        _Resources.put((cuda_stream, model))
        logger.error("Execution Error: {} \nDetailed Trace:\n{}".format(str(e), format_error(e)))
        raise e
    _Resources.put((cuda_stream, model))
    if profile_context is None:
        return results
    return results, {
        **gpu_timing,
        "thread_started_ns": thread_started_ns,
        "resource_wait_ms": (resource_acquired_ns - resource_wait_started_ns) / 1e6,
        "model_thread_wall_ms": (end_ns - start_ns) / 1e6,
        "thread_finished_ns": time.perf_counter_ns(),
    }


def thread_call(image: Union[PIL.Image.Image, np.ndarray], road_mask: np.ndarray = None,
                return_probs: bool = False) -> np.ndarray:
    return batch_call([(_Preprocessor(image), road_mask, return_probs)])[0]


def _batch_compatibility_key(prepared, return_probs):
    """Keep CUDA-Graph-static inputs and heavy output modes in separate batches."""
    output_mode = "probabilities" if return_probs else "mask-confidence"
    return (
        len(prepared.views),
        int(prepared.height),
        int(prepared.width),
        output_mode,
    )


class BatchScheduler:
    """Folds compatible requests into one GPU batch.

    A single worker thread owns the model.  The pure-async :class:`BatchQueue` keeps
    shape/output buckets safe for CUDA Graph replay and applies the selected wait
    policy before this class hands a batch to that worker.
    """

    _batch_ids = itertools.count(1)

    def __init__(self, max_batch_size: int, max_wait_seconds: float,
                 max_queue_size: int, policy: str,
                 max_queue_delay_seconds: float, adaptive_min_batch_size: int,
                 adaptive_max_misses: int,
                 adaptive_cooldown_seconds: float):
        self._queue = BatchQueue(
            max_batch_size=max_batch_size,
            max_wait_seconds=max_wait_seconds,
            max_queue_size=max_queue_size,
            policy=policy,
            max_queue_delay_seconds=max_queue_delay_seconds,
            adaptive_min_batch_size=adaptive_min_batch_size,
            adaptive_max_misses=adaptive_max_misses,
            adaptive_cooldown_seconds=adaptive_cooldown_seconds,
        )
        self._worker = None
        self._pending_by_key = {}

    def _ensure_started(self):
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())

    async def submit(self, prepared, road_mask=None, return_probs=False):
        # Count the request before the optional readiness wait so pipeline mode can
        # distinguish admitted resize work from speculative future arrivals.
        key = _batch_compatibility_key(prepared, return_probs)
        self._pending_by_key[key] = self._pending_by_key.get(key, 0) + 1
        try:
            # Opportunistic/fixed preserve early admission, allowing resize to overlap
            # the previous GPU wave. Ready-aware experimental policies wait here.
            self._ensure_started()
            if Config.batch_policy in ("pipeline", "adaptive"):
                await prepared.wait_until_model_ready()
            item = self._queue.put(
                (prepared, road_mask, return_probs),
                key,
            )
            return await item.future
        finally:
            remaining = self._pending_by_key[key] - 1
            if remaining:
                self._pending_by_key[key] = remaining
            else:
                del self._pending_by_key[key]

    async def _run(self):
        loop = asyncio.get_running_loop()
        adaptive_eligible = False
        while True:
            if Config.batch_policy == "pipeline":
                # Freeze the already-admitted population at the batch boundary.
                # Work arriving later belongs to the following CPU/GPU pipeline wave.
                pending_snapshot = dict(self._pending_by_key)
                if not adaptive_eligible:
                    pending_snapshot.clear()

                def target_batch_size(key):
                    return max(
                        1,
                        min(
                            self._queue.max_batch_size,
                            pending_snapshot.get(key, 1),
                        ),
                    )

                wait_for_target = True
            else:
                target_batch_size = self._queue.max_batch_size
                wait_for_target = False
            batch = await self._queue.collect(
                adaptive_eligible=adaptive_eligible,
                batch_size_limit=target_batch_size,
                wait_for_target=wait_for_target,
            )
            dispatch_ns = time.perf_counter_ns()
            profile_context = None
            if Config.profile_scheduler_timing:
                profile_context = {
                    "batch_id": next(self._batch_ids),
                    "dispatch_ns": dispatch_ns,
                    "executor_submitted_ns": time.perf_counter_ns(),
                }
            try:
                worker_result = await loop.run_in_executor(
                    _Executor,
                    batch_call,
                    [item.payload for item in batch],
                    profile_context,
                )
            except Exception as error:
                for item in batch:
                    if not item.future.done():
                        item.future.set_exception(error)
                await asyncio.sleep(0)
                adaptive_eligible = True
                continue
            resumed_ns = time.perf_counter_ns()
            if profile_context is None:
                results = worker_result
                worker_timing = None
            else:
                results, worker_timing = worker_result
            if len(results) != len(batch):
                error = RuntimeError(
                    f"batch returned {len(results)} results for {len(batch)} requests"
                )
                for item in batch:
                    if not item.future.done():
                        item.future.set_exception(error)
                await asyncio.sleep(0)
                adaptive_eligible = True
                continue
            for item, result in zip(batch, results):
                if not item.future.done():
                    if worker_timing is not None:
                        queue_wait_ms = (item.dequeued_ns - item.enqueue_ns) / 1e6
                        batch_formation_ms = (dispatch_ns - item.dequeued_ns) / 1e6
                        executor_queue_ms = (
                            worker_timing["thread_started_ns"]
                            - profile_context["executor_submitted_ns"]
                        ) / 1e6
                        scheduler_ms = queue_wait_ms + batch_formation_ms + executor_queue_ms
                        inference_path_ms = (resumed_ns - item.enqueue_ns) / 1e6
                        host_remainder_ms = (
                            inference_path_ms - scheduler_ms - worker_timing["gpu_total_ms"]
                        )
                        record = {
                            "batch_id": profile_context["batch_id"],
                            "batch_size": len(batch),
                            "batch_policy": Config.batch_policy,
                            "queue_depth_on_submit": item.queue_depth,
                            "queue_wait_ms": queue_wait_ms,
                            "batch_formation_ms": batch_formation_ms,
                            "executor_queue_ms": executor_queue_ms,
                            "scheduler_ms": scheduler_ms,
                            "gpu_forward_ms": worker_timing["gpu_forward_ms"],
                            "gpu_finalize_ms": worker_timing["gpu_finalize_ms"],
                            "gpu_total_ms": worker_timing["gpu_total_ms"],
                            "model_thread_wall_ms": worker_timing["model_thread_wall_ms"],
                            "resource_wait_ms": worker_timing["resource_wait_ms"],
                            "completion_dispatch_ms": (
                                resumed_ns - worker_timing["thread_finished_ns"]
                            ) / 1e6,
                            "inference_path_ms": inference_path_ms,
                            "host_remainder_ms": host_remainder_ms,
                        }
                        logger.info(
                            "PROFILE_SCHEDULER %s",
                            json.dumps(record, sort_keys=True, separators=(",", ":")),
                        )
                    item.future.set_result(result)
            # Let submit() finally blocks remove the completed wave before choosing
            # how many already-admitted requests should form the next pipeline batch.
            await asyncio.sleep(0)
            adaptive_eligible = True


_Scheduler = BatchScheduler(
    Config.max_batch_size,
    Config.max_batch_wait_ms / 1000.0,
    Config.max_queue_size,
    Config.batch_policy,
    Config.batch_max_queue_delay_ms / 1000.0,
    Config.batch_adaptive_min_batch_size,
    Config.batch_adaptive_max_misses,
    Config.batch_adaptive_cooldown_ms / 1000.0,
)

app = FastAPI()


@app.on_event("shutdown")
def _release_cuda_graphs():
    for model in _Models:
        model.predictor.release_cuda_graphs()
    if torch.cuda.is_available():
        torch.cuda.synchronize(Config.device)


async def _prepare(image):
    """Decode on the preprocessing pool and start the model resize asynchronously.

    Decode errors are rejected before scheduler admission. Pipeline/adaptive policies
    can wait for the first view before enqueue; production opportunistic mode admits
    it immediately so that the sole model thread's wait overlaps other request work.
    """
    loop = asyncio.get_running_loop()
    decoded = await loop.run_in_executor(_PreprocExecutor, _Preprocessor.decode, image)
    return _Preprocessor.fan_out(decoded, _PreprocExecutor)


async def _submit(prepared, road_mask=None, return_probs=False):
    """Enqueue one request, answering 503 rather than queueing without bound."""
    try:
        return await _Scheduler.submit(prepared, road_mask, return_probs)
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
    print("image open:", time.time() - last_time)
    last_time = time.time()
    prepared = await _prepare(image)
    print("decode + resize:", time.time() - last_time)
    last_time = time.time()
    if return_probs:
        probs = await _submit(prepared, None, True)
        print("model inference:", time.time() - last_time)
        last_time = time.time()
        response_data = await _encode_npz_response({"arr_0": probs})
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
        mask, conf = await _submit(prepared, road_mask)
        print("model inference:", time.time() - last_time)
        last_time = time.time()
        response_data = await _encode_npz_response({"mask": mask, "conf": conf})
        print("retval compress:", time.time() - last_time)
        last_time = time.time()
    print("Total:",  time.time() - start_time, "Bytes:", len(response_data)/1024, "KB")
    return Response(content=response_data, media_type="application/octet-stream")


@app.post("/predict_minimize")
async def predict(image: UploadFile = File(...)):
    last_time = start_time = time.time()
    print("--------------------")
    compressed_data = await image.read()
    print("data read:", time.time() - last_time)
    last_time = time.time()
    buffer = io.BytesIO(compressed_data)
    image = PIL.Image.open(buffer)
    print("image open:", time.time() - last_time)
    last_time = time.time()
    prepared = await _prepare(image)
    print("decode + resize:", time.time() - last_time)
    last_time = time.time()
    await _submit(prepared)
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

            prepared = await _prepare(image)
            if 'return_probs' in npdata and npdata['return_probs']:
                probs = await _Scheduler.submit(prepared, None, True)
                response_data = await _encode_npz_response({"probs": probs})
            else:
                road_mask = None
                if 'road_mask' in npdata and npdata['road_mask'].shape == image.size[::-1]:
                    road_mask = npdata['road_mask']
                mask, conf = await _Scheduler.submit(prepared, road_mask)
                response_data = await _encode_npz_response({"mask": mask, "conf": conf})
            await websocket.send_bytes(response_data)
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
