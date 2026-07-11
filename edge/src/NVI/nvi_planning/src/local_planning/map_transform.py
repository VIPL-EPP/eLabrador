import numpy  as np
import nvi_octomap
from .semantic_config import *
from .config import SemanticConfig, MetricConfig
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

SCONFIG = SemanticConfig()
SCONFIG.parse_json(CURRENT_DIR+"/config/dataconfig_mapillary_extend.json")
MCONFIG = MetricConfig(1)

def _get_semantic_from_color(color):
    '''
    color: (r, g, b)
    return: semantic string
    '''
    for semantic in COLOR_MAP.keys():
        if COLOR_MAP[semantic] == color:
            return semantic
    # print("warning: no semantic color",color,"found.")
    return None

def _get_list2d(shape,template):
    template_list = []
    for i in range(shape[0]):
        sub_list  = []
        for j in range(shape[1]):
            sub_list.append(template.copy())
        template_list.append(sub_list)
    return template_list

def octree2gridmap(octree):
    metric_max = octree.get_metric_max()
    metric_min = octree.get_metric_min()
    resolution =  0.2 # super parameter
    width = int((metric_max.x() - metric_min.x())/resolution) +1
    height = int((metric_max.y() - metric_min.y())/resolution) +1
    origin_position_x = metric_min.x()
    origin_position_y = metric_min.y()
    map_data = np.ones((height,width),dtype=np.int8)*-1
    leaf_iter = octree.begin_leafs()
    end_leaf_iter = octree.end_leafs()
    map_semantic =_get_list2d((height,width),dict())
    while leaf_iter != end_leaf_iter:
        x,y,z = leaf_iter.get_x(),leaf_iter.get_y(),leaf_iter.get_z()
        if leaf_iter.get_z() > 0.2:
            leaf_iter.next()
            continue
        node_color = leaf_iter.get_color()
        semantic = _get_semantic_from_color((node_color.b, node_color.g,node_color.r))
        if semantic is None:
            leaf_iter.next()
            continue
        grid_color = COLOR_GRIDMAP[semantic]
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)
        if grid_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][grid_color] = 1
        else:
            map_semantic[y_grid][x_grid][grid_color] +=1
        leaf_iter.next()
    
    for j in range(height):
        for i in range(width):
            if map_semantic[j][i]:
                map_data[j][i] = max(map_semantic[j][i], key=map_semantic[j][i].get)
    return (map_data,resolution,(origin_position_x,origin_position_y))

def octree2localsemanticmap(octree, location):
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution) + 5
    height = int(2*Y_RADIUS/resolution) + 5
    origin_position_x = bbx_min.x()
    origin_position_y = bbx_min.y()
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_semantic = _get_list2d((height, width), dict())

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy()<0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic = SCONFIG.get_macro(node_color)
        if semantic is None:
            leaf_bbx_iter.next()
            continue
        grid_color = COLOR_GRIDMAP[semantic]
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)
        if grid_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][grid_color] = 1
        else:
            map_semantic[y_grid][x_grid][grid_color] += 1
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_semantic[j][i]:
                map_data[j][i] = max(map_semantic[j][i],
                                     key=map_semantic[j][i].get)
                                     
    return (map_data, resolution, (origin_position_x, origin_position_y))

def octree2localsemanticmap_complete(octree, location):
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution) + 5
    height = int(2*Y_RADIUS/resolution) + 5
    origin_position_x = bbx_min.x()
    origin_position_y = bbx_min.y()
    map_data = np.ones((height, width,3), dtype=np.int8)*-1
    map_semantic = _get_list2d((height, width), dict())

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy()<0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        # semantic = SCONFIG.get_macro(node_color)
        # if semantic is None:
        #     leaf_bbx_iter.next()
        #     continue
        # grid_color = COLOR_GRIDMAP[semantic]
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)
        if node_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][node_color] = 1
        else:
            map_semantic[y_grid][x_grid][node_color] += 1
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_semantic[j][i]:
                map_data[height-j-1][i] = np.array(max(map_semantic[j][i],
                                     key=map_semantic[j][i].get))
                                     
    return (map_data, resolution, (origin_position_x, origin_position_y))
    

# --- Ego-aligned semantic map functions ---
def octree2localsemanticmap_ego(octree, location, yaw):
    """Generate an ego-aligned local semantic grid map.

    Ego frame convention (match existing system):
      x_ego: right
      y_ego: forward

    The output grid axes are aligned with the ego frame. Bounding-box query is
    still performed in world frame for efficiency.

    Args:
        octree: nvi_octomap octree
        location: (loc_x, loc_y, loc_z) in world/VIO frame
        yaw: heading angle in world frame (radians)

    Returns:
        (map_data, resolution, (origin_x, origin_y))
        where origin_x/y are in ego frame.
    """
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5

    # Query bbx in world frame (same as the non-ego version)
    bbx_min = nvi_octomap.Point3d(loc_x - X_RADIUS, loc_y - Y_RADIUS, loc_z - 2.5)
    bbx_max = nvi_octomap.Point3d(loc_x + X_RADIUS, loc_y + Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2 * X_RADIUS / resolution) + 5
    height = int(2 * Y_RADIUS / resolution) + 5

    # Define grid origin in ego frame (lower-left corner), matching the padding
    # convention used by octree2localprmap_height_ego for strict grid alignment.
    origin_position_x = (-X_RADIUS) - resolution * 2
    origin_position_y = (-Y_RADIUS) - resolution * 2

    map_data = np.ones((height, width), dtype=np.int8) * -1
    map_semantic = _get_list2d((height, width), dict())
    map_dynamic_semantic = _get_list2d((height, width), dict())
    dynamic_macros = {'human', 'rider', 'vehicle'}

    c = np.cos(yaw)
    s = np.sin(yaw)

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()

    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy() < 0.5:
            leaf_bbx_iter.next()
            continue

        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic = SCONFIG.get_macro(node_color)
        if semantic is None:
            leaf_bbx_iter.next()
            continue

        grid_color = COLOR_GRIDMAP[semantic]

        # World -> ego transform (x_ego right, y_ego forward)
        dx = x - loc_x
        dy = y - loc_y
        x_ego = c * dx + s * dy
        y_ego = -s * dx + c * dy

        x_grid = int((x_ego - origin_position_x) / resolution)
        y_grid = int((y_ego - origin_position_y) / resolution)

        if x_grid < 0 or x_grid >= width or y_grid < 0 or y_grid >= height:
            leaf_bbx_iter.next()
            continue

        if grid_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][grid_color] = 1
        else:
            map_semantic[y_grid][x_grid][grid_color] += 1

        if semantic in dynamic_macros:
            if grid_color not in map_dynamic_semantic[y_grid][x_grid]:
                map_dynamic_semantic[y_grid][x_grid][grid_color] = 1
            else:
                map_dynamic_semantic[y_grid][x_grid][grid_color] += 1

        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_dynamic_semantic[j][i]:
                map_data[j][i] = max(
                    map_dynamic_semantic[j][i],
                    key=map_dynamic_semantic[j][i].get
                )
            elif map_semantic[j][i]:
                map_data[j][i] = max(map_semantic[j][i], key=map_semantic[j][i].get)

    return (map_data, resolution, (origin_position_x, origin_position_y))

def octree2localsemanticmap_complete_ego(octree, location, yaw):
    """Generate an ego-aligned local semantic RGB image map.

    Ego frame convention (match existing system):
      x_ego: right
      y_ego: forward

    The output grid axes are aligned with the ego frame. Bounding-box query is
    still performed in world frame for efficiency.

    Args:
        octree: nvi_octomap octree
        location: (loc_x, loc_y, loc_z) in world/VIO frame
        yaw: heading angle in world frame (radians)

    Returns:
        (map_data, resolution, (origin_x, origin_y))
        where origin_x/y are in ego frame.
    """
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5

    # Query bbx in world frame (same as the non-ego version)
    bbx_min = nvi_octomap.Point3d(loc_x - X_RADIUS, loc_y - Y_RADIUS, loc_z - 2.5)
    bbx_max = nvi_octomap.Point3d(loc_x + X_RADIUS, loc_y + Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2 * X_RADIUS / resolution) + 5
    height = int(2 * Y_RADIUS / resolution) + 5

    # Define grid origin in ego frame (lower-left corner), matching the padding
    # convention used by octree2localprmap_height_ego for strict grid alignment.
    origin_position_x = (-X_RADIUS) - resolution * 2
    origin_position_y = (-Y_RADIUS) - resolution * 2

    map_data = np.ones((height, width, 3), dtype=np.int8) * -1
    map_semantic = _get_list2d((height, width), dict())

    c = np.cos(yaw)
    s = np.sin(yaw)

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()

    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy() < 0.5:
            leaf_bbx_iter.next()
            continue

        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)

        # World -> ego transform (x_ego right, y_ego forward)
        dx = x - loc_x
        dy = y - loc_y
        x_ego = c * dx + s * dy
        y_ego = -s * dx + c * dy

        x_grid = int((x_ego - origin_position_x) / resolution)
        y_grid = int((y_ego - origin_position_y) / resolution)

        if x_grid < 0 or x_grid >= width or y_grid < 0 or y_grid >= height:
            leaf_bbx_iter.next()
            continue

        if node_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][node_color] = 1
        else:
            map_semantic[y_grid][x_grid][node_color] += 1
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_semantic[j][i]:
                map_data[height - j - 1][i] = np.array(
                    max(map_semantic[j][i], key=map_semantic[j][i].get)
                )

    return (map_data, resolution, (origin_position_x, origin_position_y))
    

def octree2localprmap(octree, location):
    loc_x, loc_y, loc_z = location
    X_RADIUS  = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution)   + 5
    height = int(2*Y_RADIUS/resolution)  + 5
    origin_position_x = bbx_min.x() - resolution*2
    origin_position_y = bbx_min.y() - resolution *2
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_degree = _get_list2d((height, width), list())

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy()<0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        # if x < bbx_min.x() or y < bbx_min.y() or z < bbx_min.z():
        #     print('warning l: ',x,y,z,'|',bbx_min.x(), bbx_min.y(), bbx_min.z())
        # if x > bbx_max.x() or y > bbx_max.y() or z > bbx_max.z():
        #     print('warning g: ', x, y, z, '|',
        #           bbx_max.x(), bbx_max.y(), bbx_max.z())
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic_degree = SCONFIG.get_degree(node_color)
        if semantic_degree is None:
            leaf_bbx_iter.next()
            continue
        metric_degree = MCONFIG.get_degree(z-loc_z)
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)

        map_degree[y_grid][x_grid].append(semantic_degree*metric_degree)
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_degree[j][i]:
                map_data[j][i] = int(
                    sum(map_degree[j][i])/len(map_degree[j][i])*100)

    return (map_data, resolution, (origin_position_x, origin_position_y))

def octree2localprmap_height(octree, location):
    loc_x, loc_y, loc_z = location
    X_RADIUS  = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution)   + 5
    height = int(2*Y_RADIUS/resolution)  + 5
    origin_position_x = bbx_min.x() - resolution*2
    origin_position_y = bbx_min.y() - resolution *2
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_data_height = np.ones((height, width), dtype=float)*-4.04
    map_degree = _get_list2d((height, width), list())

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy()<0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        # if x < bbx_min.x() or y < bbx_min.y() or z < bbx_min.z():
        #     print('warning l: ',x,y,z,'|',bbx_min.x(), bbx_min.y(), bbx_min.z())
        # if x > bbx_max.x() or y > bbx_max.y() or z > bbx_max.z():
        #     print('warning g: ', x, y, z, '|',
        #           bbx_max.x(), bbx_max.y(), bbx_max.z())
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic_degree = SCONFIG.get_degree(node_color)
        if semantic_degree is None:
            leaf_bbx_iter.next()
            continue
        metric_degree = MCONFIG.get_degree(z-loc_z)
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)

        map_degree[y_grid][x_grid].append(semantic_degree*metric_degree)
        map_data_height[y_grid][x_grid]= max(map_data_height[y_grid][x_grid],z-loc_z) 
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_degree[j][i]:
                map_data[j][i] = int(
                    sum(map_degree[j][i])/len(map_degree[j][i])*100)
    
    map_data_height[map_data_height>0] = 0 # ignore the obstacles higher than camera.
    max_height, min_height = 0,-4.04 
    map_data_height = ((map_data_height - min_height)*101/(max_height-min_height)-1).astype(np.int8)
    return (map_data, resolution, (origin_position_x, origin_position_y),map_data_height)

 # --- Mirror octree2localprmap_height, but publish the cost map in the ego-aligned local frame. ---
 # Keep the existing convention: x points right and y points forward, consistent with local_planner/quaternion2cartesian.
def octree2localprmap_height_ego(octree, location, yaw):
    """Generate an ego-aligned local cost/height map.
    
    Ego frame convention (match existing system):
      x_ego: right
      y_ego: forward

    The output grid axes are aligned with the ego frame (no additional rotation needed).
    Bounding-box query is still performed in world frame for efficiencyO(leafs) efficiency.

    Args:
        octree: nvi_octomap octree
        location: (loc_x, loc_y, loc_z) in world/VIO frame
        yaw: heading angle in world frame (radians)

    Returns:
        (map_data, resolution, (origin_x, origin_y), map_data_height)
        where origin_x/y are in ego frame.
    """
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5

    # Query bbx in world frame (same as the non-ego version)
    bbx_min = nvi_octomap.Point3d(loc_x - X_RADIUS, loc_y - Y_RADIUS, loc_z - 2.5)
    bbx_max = nvi_octomap.Point3d(loc_x + X_RADIUS, loc_y + Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2 * X_RADIUS / resolution) + 5
    height = int(2 * Y_RADIUS / resolution) + 5

    # Define grid origin in ego frame (lower-left corner), matching the padding in the original impl.
    origin_position_x = (-X_RADIUS) - resolution * 2
    origin_position_y = (-Y_RADIUS) - resolution * 2

    map_data = np.ones((height, width), dtype=np.int8) * -1
    map_data_height = np.ones((height, width), dtype=float) * -4.04
    map_degree = _get_list2d((height, width), list())

    c = np.cos(yaw)
    s = np.sin(yaw)

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()

    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy() < 0.5:
            leaf_bbx_iter.next()
            continue

        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()

        # Semantic degree (same as original)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic_degree = SCONFIG.get_degree(node_color)
        if semantic_degree is None:
            leaf_bbx_iter.next()
            continue

        metric_degree = MCONFIG.get_degree(z - loc_z)

        # World -> ego transform (x_ego right, y_ego forward)
        dx = x - loc_x
        dy = y - loc_y
        x_ego = c * dx + s * dy
        y_ego = -s * dx + c * dy

        x_grid = int((x_ego - origin_position_x) / resolution)
        y_grid = int((y_ego - origin_position_y) / resolution)

        # Robust bounds check (should be in-range, but guard against edge cases)
        if x_grid < 0 or x_grid >= width or y_grid < 0 or y_grid >= height:
            leaf_bbx_iter.next()
            continue

        map_degree[y_grid][x_grid].append(semantic_degree * metric_degree)
        map_data_height[y_grid][x_grid] = max(map_data_height[y_grid][x_grid], z - loc_z)

        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_degree[j][i]:
                map_data[j][i] = int(sum(map_degree[j][i]) / len(map_degree[j][i]) * 100)

    # Keep height encoding consistent with original implementation
    map_data_height[map_data_height > 0] = 0  # ignore the obstacles higher than camera.
    max_height, min_height = 0, -4.04
    map_data_height = ((map_data_height - min_height) * 101 / (max_height - min_height) - 1).astype(np.int8)

    return (map_data, resolution, (origin_position_x, origin_position_y), map_data_height)

def octree2localprmap2(octree, location):
    loc_x, loc_y, loc_z = location
    X_RADIUS = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution) + 4
    height = int(2*Y_RADIUS/resolution) + 4
    origin_position_x = bbx_min.x()
    origin_position_y = bbx_min.y()
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_degree = _get_list2d((height, width), [0.0,0.0])

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        metric_prob = leaf_bbx_iter.get_occupancy()
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        # if x < bbx_min.x() or y < bbx_min.y() or z < bbx_min.z():
        #     print('warning l: ',x,y,z,'|',bbx_min.x(), bbx_min.y(), bbx_min.z())
        # if x > bbx_max.x() or y > bbx_max.y() or z > bbx_max.z():
        #     print('warning g: ', x, y, z, '|',
        #           bbx_max.x(), bbx_max.y(), bbx_max.z())
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic_degree = SCONFIG.get_degree(node_color)
        if semantic_degree is None:
            leaf_bbx_iter.next()
            continue
        metric_degree = MCONFIG.get_degree(z-loc_z)
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)

        map_degree[y_grid][x_grid][0] += semantic_degree*metric_degree*metric_prob
        map_degree[y_grid][x_grid][1] +=metric_prob
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_degree[j][i][1]>0:
                map_data[j][i] = int(map_degree[j][i][0]/map_degree[j][i][1]*100)

    return (map_data, resolution, (origin_position_x, origin_position_y))

def _potential(x):
    if x>=-11:
        return np.exp(-0.1*(x+1))
    else:
        return 1

def octree2localpotentialmap(octree, location,direction):
    loc_x, loc_y, loc_z = location
    dir_x, dir_y = direction[0],direction[1]
    dir_len = (dir_x**2+dir_y**2)**0.5
    dir_x, dir_y = dir_x/dir_len, dir_y/dir_len
    X_RADIUS = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution) + 4
    height = int(2*Y_RADIUS/resolution) + 4
    origin_position_x = bbx_min.x()
    origin_position_y = bbx_min.y()
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_degree = _get_list2d((height, width), list())
    map_potential = np.ones((height, width), dtype=np.float)*-1

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy() < 0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        # if x < bbx_min.x() or y < bbx_min.y() or z < bbx_min.z():
        #     print('warning l: ',x,y,z,'|',bbx_min.x(), bbx_min.y(), bbx_min.z())
        # if x > bbx_max.x() or y > bbx_max.y() or z > bbx_max.z():
        #     print('warning g: ', x, y, z, '|',
        #           bbx_max.x(), bbx_max.y(), bbx_max.z())
        node_location = (x, y, z)
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic_degree = SCONFIG.get_degree(node_color)
        if semantic_degree is None:
            leaf_bbx_iter.next()
            continue
        metric_degree = MCONFIG.get_degree(z-loc_z)
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)

        map_degree[y_grid][x_grid].append(semantic_degree*metric_degree)
        if map_potential[y_grid][x_grid] == -1:
            project_len = dir_x*(x-loc_x)+dir_y*(y-loc_y)
            # if project_len >=0:
            #     print('project len',project_len)
            map_potential[y_grid][x_grid] = _potential(dir_x*(x-loc_x)+dir_y*(y-loc_y))
        leaf_bbx_iter.next()
    

    for j in range(height):
        for i in range(width):
            if map_degree[j][i]:
                # map_degree[j][i] = min(map_degree[j][i]+map_potential[j][i],1)
                degree = sum(map_degree[j][i])/len(map_degree[j][i])
                degree = min(degree+map_potential[j][i], 1)
                map_data[j][i] = int(degree*100)
            
                # map_data[j][i] = int(
                #     sum(map_degree[j][i])/len(map_degree[j][i])*100)
                # if map_potential[j][i]<1:
                #     map_data[j][i] *= map_potential[j][i]
                # else:
                #     map_data[j][i] = max(map_data[j][i],90)
                # # map_data[j][i] = int(100*map_potential[j][i])
                # map_degree[j][i].append(map_potential[j][i])
                
    return (map_data, resolution, (origin_position_x, origin_position_y))

def get_cell_cordinate(location, resolution):
    loc_x, loc_y, loc_z = location
    x_grid = int(loc_x/resolution)
    y_grid = int(loc_y/resolution)
    z_grid = int(loc_z/resolution)
    loc_x, loc_y, loc_z = x_grid*resolution, y_grid*resolution, z_grid*resolution
    return loc_x, loc_y, loc_z

def octree2local_semantic_height_map(octree, location, resolution = 0.2):
    loc_x, loc_y, loc_z = get_cell_cordinate(location, resolution)
    X_RADIUS = 7.5
    Y_RADIUS = 7.5
    bbx_min = nvi_octomap.Point3d(loc_x-X_RADIUS, loc_y-Y_RADIUS, loc_z-2.5)
    bbx_max = nvi_octomap.Point3d(loc_x+X_RADIUS, loc_y+Y_RADIUS, loc_z+0.2)

    resolution = 0.2  # super parameter
    width = int(2*X_RADIUS/resolution) + 5
    height = int(2*Y_RADIUS/resolution) + 5
    origin_position_x = bbx_min.x()
    origin_position_y = bbx_min.y()
    map_data = np.ones((height, width), dtype=np.int8)*-1
    map_semantic = _get_list2d((height, width), dict())

    leaf_bbx_iter = octree.begin_leafs_bbx(bbx_min, bbx_max)
    end_bbx_leaf_iter = octree.end_leafs_bbx()
    # print('new ------------------------------------')
    while leaf_bbx_iter != end_bbx_leaf_iter:
        if leaf_bbx_iter.get_occupancy()<0.5:
            leaf_bbx_iter.next()
            continue
        x, y, z = leaf_bbx_iter.get_x(), leaf_bbx_iter.get_y(), leaf_bbx_iter.get_z()
        node_color = leaf_bbx_iter.get_color()
        node_color = (node_color.b, node_color.g, node_color.r)
        semantic = SCONFIG.get_semantic(node_color)
        if semantic is None:
            leaf_bbx_iter.next()
            continue
        grid_color = COLOR_GRIDMAP[semantic]
        x_grid = int((x-origin_position_x)/resolution)
        y_grid = int((y-origin_position_y)/resolution)
        if grid_color not in map_semantic[y_grid][x_grid]:
            map_semantic[y_grid][x_grid][grid_color] = 1
        else:
            map_semantic[y_grid][x_grid][grid_color] += 1
        leaf_bbx_iter.next()

    for j in range(height):
        for i in range(width):
            if map_semantic[j][i]:
                map_data[j][i] = max(map_semantic[j][i],
                                     key=map_semantic[j][i].get)
                                     
    return (map_data, resolution, (origin_position_x, origin_position_y))

if __name__ == '__main__':
    _get_semantic_from_color((244, 35, 232))

