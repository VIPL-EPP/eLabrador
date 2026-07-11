from easydict import EasyDict

Mask2FormerConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:0'
)

Mask2FormerDetectron2Config=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:0',
    config_file='configs/mask2former_detectron2_model.yaml'
)

QwenVLConfig=EasyDict(
    num_thread=1, # 目前无法支持多线程，hugingface内部代码线程不安全
    device='cuda:1'
)