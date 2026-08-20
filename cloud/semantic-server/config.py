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
    float32_matmul_precision=os.getenv('NVI_FLOAT32_MATMUL_PRECISION', 'high')
)

QwenVLConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:1'
)