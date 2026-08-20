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
    # 请求级 batch。一个 TTA pass 的 kernel 启动数几乎与 batch 无关，因此把并发
    # 请求合到一批可以摊薄启动开销。max_batch_size=1 恢复逐请求执行。
    max_batch_size=int(os.getenv('NVI_MAX_BATCH_SIZE', '4')),
    # 组批额外等待窗口。0 表示只收走上一批执行期间堆积的请求，不给低负载加延迟。
    max_batch_wait_ms=float(os.getenv('NVI_MAX_BATCH_WAIT_MS', '0')),
    # 有界队列上限，超出返回 503。
    max_queue_size=int(os.getenv('NVI_MAX_QUEUE_SIZE', '32'))
)

QwenVLConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:1'
)