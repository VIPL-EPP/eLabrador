import os
from .mask2former_detector import Detector as mask2formerDetector
try:
    from .mmcv_detector import Detector as mmcvDetector
except ImportError:
    mmcvDetector = None
import mmcv

def build_detector(model_name, dataset, **kwargs):
    if model_name == 'mask2former':
        return mask2formerDetector(**kwargs)
    elif model_name == 'EfficientPS':
        assert mmcvDetector, "Please install EfficientPS to use mmcvDetector"
        return mmcvDetector(config_path, **kwargs)

__all__ = ['mask2formerDetector', 'mmcvDetector', 'build_detector']
