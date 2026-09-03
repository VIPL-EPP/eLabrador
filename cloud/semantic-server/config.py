import os

from easydict import EasyDict

Mask2FormerConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:0'
)

Mask2FormerDetectron2Config=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:0',
    config_file='configs/mask2former_detectron2_model.yaml',
    # float32 矩阵乘精度。'high' 让 cuBLAS 在 H100 上选择 TF32 Tensor Core kernel，
    # 'highest' 保持 FP32 FMA。在固定测试输入上 'high' 的分割 mask 与 'highest'
    # 逐像素一致，概率张量最大绝对偏差 1.41e-3；带标注验证集上的任务精度未评估。
    float32_matmul_precision=os.getenv('NVI_FLOAT32_MATMUL_PRECISION', 'high'),
    # Optional mixed precision for the BF16-capable parts of the model. Keep disabled
    # by default until labelled-set mIoU is validated. On the fixed 1024x768/no-TTA
    # H100 Graph path, bfloat16 improved model P50 by about 4.7% on the test fixture.
    autocast_dtype=os.getenv('NVI_AUTOCAST_DTYPE', 'none').lower(),
    # Swin attention implementation is read directly by the patched dependency.
    # Keep legacy as the production default until labelled-set mIoU is validated.
    swin_attention_impl=os.getenv('NVI_SWIN_ATTENTION_IMPL', 'legacy').lower(),
    # Fixed-shape local Inductor graphs are also implemented in the patched
    # dependency. Keep both opt-in until labelled-set mIoU is validated.
    swin_ffn_impl=os.getenv('NVI_SWIN_FFN_IMPL', 'legacy').lower(),
    decoder_pointwise_impl=os.getenv(
        'NVI_DECODER_POINTWISE_IMPL', 'legacy'
    ).lower(),
    # Opt-in fixed-shape MS-Deform forward kernels. h100-fixed-fp32 uses a
    # 128-thread block; bw1000-fixed-fp32 uses the independently measured
    # 64-thread block. The extension checks every production dimension.
    msdeform_impl=os.getenv('NVI_MSDEFORM_IMPL', 'legacy').lower(),
    # Fuse the two encoder residual adds with their LayerNorm reductions.
    msdeform_norm_impl=os.getenv(
        'NVI_MSDEFORM_NORM_IMPL', 'legacy'
    ).lower(),
    # Keep the encoder FFN residual/LayerNorm in FP32 while allowing only its
    # two fixed-shape GEMMs and ReLU to use a compiled BF16 path.
    msdeform_ffn_impl=os.getenv(
        'NVI_MSDEFORM_FFN_IMPL', 'legacy'
    ).lower(),
    # Fuse fixed-size bilinear interpolation with its following pointwise op.
    upsample_pointwise_impl=os.getenv(
        'NVI_UPSAMPLE_POINTWISE_IMPL', 'legacy'
    ).lower(),
    # Batch the semantic query aggregation/final resize for requests with the
    # same input and output geometry. Keep legacy until labelled mIoU is checked.
    semantic_batch_impl=os.getenv(
        'NVI_SEMANTIC_BATCH_IMPL', 'legacy'
    ).lower(),
    # 请求级 batch。固定单次前向的 kernel 启动数几乎与 batch 无关，因此把并发
    # 请求合到一批可以摊薄启动开销。max_batch_size=1 恢复逐请求执行。
    max_batch_size=int(os.getenv('NVI_MAX_BATCH_SIZE', '4')),
    # H100 A/B 后默认保留机会式早入队：它能让 resize/响应与 GPU 波次重叠。pipeline、
    # adaptive 和 fixed 作为实验策略保留，但不会在未显式启用时增加等待。
    batch_policy=os.getenv('NVI_BATCH_POLICY', 'opportunistic').lower(),
    # pipeline/adaptive/fixed 的最大组批等待；opportunistic 忽略该值。
    max_batch_wait_ms=float(os.getenv('NVI_MAX_BATCH_WAIT_MS', '0')),
    # ready 请求允许在 batch 队列中停留的最长时间；0 表示只受上面的窗口约束。
    batch_max_queue_delay_ms=float(
        os.getenv('NVI_BATCH_MAX_QUEUE_DELAY_MS', '50')
    ),
    # 当前 H100 实测 B2 53.12 req/s，低于持续 B1 的 55.35 req/s；因此只有
    # ready batch 已达到 2 时，才值得额外等待去尝试 B3/B4。
    batch_adaptive_min_batch_size=int(
        os.getenv('NVI_BATCH_ADAPTIVE_MIN_BATCH_SIZE', '2')
    ),
    # 自适应等待连续失败后暂时退回机会式组批，避免在不可能凑批的 closed-loop
    # 流量上为每个请求重复支付等待窗口；冷却后探测一次以适应负载变化。
    batch_adaptive_max_misses=int(
        os.getenv('NVI_BATCH_ADAPTIVE_MAX_MISSES', '2')
    ),
    batch_adaptive_cooldown_ms=float(
        os.getenv('NVI_BATCH_ADAPTIVE_COOLDOWN_MS', '5000')
    ),
    # 有界队列上限，超出返回 503。
    max_queue_size=int(os.getenv('NVI_MAX_QUEUE_SIZE', '32')),
    # CUDA Graph 捕获和回放，消除 kernel 启动开销。
    use_cuda_graph=os.getenv('NVI_USE_CUDA_GRAPH', 'true').lower() in ('true', '1', 'yes'),
    # 可限制需要常驻的 Graph batch。当前 BW1000 验收因分配设备上的外部 HBM
    # 占用只保留 B1 Graph，B2–B4 回退 eager；H100 默认与 max_batch_size 相同。
    cuda_graph_max_batch_size=int(os.getenv(
        'NVI_CUDA_GRAPH_MAX_BATCH_SIZE',
        os.getenv('NVI_MAX_BATCH_SIZE', '4')
    )),
    # JPEG 解码与 resize 的线程数。该部分不持有模型状态，从推理线程移出后
    # 可与 GPU 前向重叠，并在并发请求之间并行。设为 1 恢复串行预处理。
    preproc_threads=int(os.getenv('NVI_PREPROC_THREADS', '4')),
    # NPZ 响应使用 Deflate level 1，并在独立线程池中编码。线程池与预处理、模型
    # 线程隔离，使上一批响应压缩可以和下一批 GPU 推理重叠。
    npz_compression_level=int(os.getenv('NVI_NPZ_COMPRESSION_LEVEL', '1')),
    compress_threads=int(os.getenv('NVI_COMPRESS_THREADS', '4')),
    # Profile-only scheduler/GPU timing. Disabled by default because CUDA Events,
    # synchronization and per-request JSON logs perturb the measured path.
    profile_scheduler_timing=os.getenv(
        'NVI_PROFILE_SCHEDULER_TIMING', 'false'
    ).lower() in ('true', '1', 'yes'),
    # 启动时预先捕获 CUDA Graph 的输入尺寸，格式 WxH，逗号分隔，空字符串关闭。
    # Graph 按 (尺度, batch 内逐输入 shape/输出尺寸, 翻转) 索引，未捕获的键在首次命中的请求
    # 内完成捕获，实测该请求耗时 1.31 s，稳态为 0.24 s。列出的尺寸在启动时捕获，
    # 未列出的尺寸仍在首次使用时捕获。
    warmup_shapes=os.getenv('NVI_WARMUP_SHAPES', '640x480')
)

QwenVLConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:1'
)
