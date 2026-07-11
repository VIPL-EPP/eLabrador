from blind_guide_modules import build_detector
import cv2
import mmcv
import numpy as np


if __name__ == "__main__":
    detector = build_detector("mask2former", "mapillary", debug_mode=True)

    # d455
    transform_matrix = np.matrix([[393.955,   0.   , 328.337],
                                 [  0.   , 393.955, 238.703],
                                 [  0.   ,   0.   ,   1.   ]])
    image = cv2.imread("a.jpg")
    
    pred, conf, additional = detector.predict(image, color='bgr', return_color=True, depth=None,
                                                transform_matrix=transform_matrix, instance_pred=None)

    cv2.imwrite("pred.png", pred)