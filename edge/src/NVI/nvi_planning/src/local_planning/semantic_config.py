from collections import OrderedDict

COLOR_MAP = OrderedDict((("road", (128, 64, 128)),
                         ("sidewalk", (244, 35, 232)),
                         ("building", (70, 70, 70)),
                         ("wall", (102, 102, 156)),
                         ("fence", (190, 153, 153)),
                         ("pole", (153, 153, 153)),
                         ("traffic light", (250, 170, 30)),
                         ("traffic sign", (220, 220, 0)),
                         ("vegetation", (107, 142, 35)),
                         ("terrain", (152, 251, 152)),
                         ("sky", (70, 130, 180)),
                         ("person", (220, 20, 60)),
                         ("rider", (255, 0, 0)),
                         ("car", (0, 0, 142)),
                         ("truck", (0, 0, 70)),
                         ("bus", (0, 60, 100)),
                         ("train", (0, 80, 100)),
                         ("motorcycle", (0, 0, 230)),
                         ("bicycle", (119, 11, 32)),
                         ("crosswalk", (140, 140, 250)),
                         # crosswalk class in not labeled in cityscapes, this color is only available for fuse detector.
                         ("unlabeled", (0, 0, 0))))

# green: 120, red: 130, orange: 170, yellow: 200
_WHITE = 0
_GRAY = 80
_GREEN = 120
_RED  = 130
_ORANGE = 170
_YELLOW = 200
# COLOR_GRIDMAP = OrderedDict((("road", 0),
#                          ("sidewalk", 0),
#                          ("building", 80),
#                          ("wall", 80),
#                          ("fence", 80),
#                          ("pole", 80),
#                          ("traffic light", _YELLOW),
#                          ("traffic sign", _YELLOW),
#                          ("vegetation", _GREEN),
#                          ("terrain", _GREEN),
#                          ("sky", -1),
#                          ("person", _ORANGE),
#                          ("rider", _ORANGE),
#                          ("car", _RED),
#                          ("truck", _RED),
#                          ("bus", _RED),
#                          ("train", _RED),
#                          ("motorcycle", _RED),
#                          ("bicycle", _RED),
#                          ("crosswalk", 0),
#                          # crosswalk class in not labeled in cityscapes, this color is only available for fuse detector.
#                          ("unlabeled", 80)))

COLOR_GRIDMAP = OrderedDict((("animal", _ORANGE), ("barrier", _GRAY), ("flat", _WHITE), ("structure", _GRAY), ("human", _ORANGE), ("rider", _ORANGE), (
    "marking", _WHITE), ("nature", _GREEN), ("object", _GRAY), ("support", _GRAY), ("traffic-sign", _YELLOW), ("vehicle", _RED), ("void", _WHITE)))

# Legacy label mapping kept here during development:
COLOR_VOICE = OrderedDict(((_WHITE, "road"), (_GRAY, "obstacle"), (_GREEN, "vegetation"),   (_RED, "vehicle"), (_ORANGE, "person"), (_YELLOW, 'traffic sign')))
