import cv2
import math
import numpy as np
'''
module for drawing geometry on grid map (array with data type int8)

all input data  range from -254 - 255
'''


def _convex_hull(points):
        pList = []
        for point in points:
            pList.append(point)
        pList.sort()
        rs = []  # set()
        tmp = 0
        currentDegree, curminDegree, degree = 0, 360, 0
        p0, p1 = pList[0],  (0, 0)
        while True:
            tmp_ = 0
            for j in range(len(pList)):
                if tmp == j:
                    continue
                p1 = pList[j]
                degree = _calculate_bearing2point(
                    currentDegree, p0[0], p0[1], p1[0], p1[1])
                if degree < curminDegree:
                    curminDegree = degree
                    tmp_ = j
            tmp = tmp_
            currentDegree += curminDegree
            curminDegree = 360
            if currentDegree >= 360:
                currentDegree -= 360
            p0 = pList[tmp]
            rs.append(p0)
            # print(p0[0]," ",p0[1])
            if tmp == 0:
                break
        return rs


def _calculate_bearing2point(currentBearing, currentX, currentY, targetX, targetY):
    vectorX = targetX - currentX
    vectorY = targetY - currentY
    degree = 180 * \
        math.acos(vectorY / math.sqrt(vectorX *
                                      vectorX + vectorY * vectorY)) / math.pi
    if vectorX < 0:
        degree = 360 - degree
    cbtp = degree - currentBearing
    if cbtp < 0:
        return 360 + degree
    else:
        return cbtp

def draw_polygon(map_data,points,color = 100,filling=True):
    '''
    drawing polygon according to input points set, the polygon is the minimum polygon including all points.
    '''
    ordered_points = _convex_hull(points)
    cv2.fillPoly(map_data, [np.array(ordered_points)],color)
    # cv2.polylines(map_data, [np.array(ordered_points)], filling, color)

def draw_point(map_data,point,radius=3,color=100):
    '''
    drawing point acoording to input point
    '''
    map_data = np.asarray(map_data, dtype=np.uint8)
    cv2.circle(map_data,point,radius,color,-1)

def draw_arrow(map_data, point, direction, length, color):
    # Convert map_data to np.uint8 if necessary
    map_data = np.asarray(map_data, dtype=np.uint8)
    end_point = (point[0] + int(direction[0] * length), point[1] + int(direction[1] * length))
    cv2.arrowedLine(map_data, point, end_point, color, 2)
    return map_data

def median_filter(map_data,ksize=3):
    '''
    return: the filtered map
    '''
    map_data =  cv2.medianBlur(map_data.astype(np.uint8),ksize)
    return map_data.astype(np.int8)

def edge_filter(map_data,ksize=1,filter_type='sobel',LOW_HEIGHT=30,HIGH_HEIGHT=120):
    '''
    return: the detected edges in map
    '''
    if filter_type == 'sobel':
        x = cv2.Sobel(map_data.astype(np.uint8), cv2.CV_16S, 1, 0,ksize=ksize)
        y = cv2.Sobel(map_data.astype(np.uint8), cv2.CV_16S, 0, 1,ksize=ksize) 
        x, y = np.abs(x), np.abs(y)
        map_data = cv2.max(x,y)
        map_data[map_data>HIGH_HEIGHT] = 0
        map_data[map_data<LOW_HEIGHT] = 0

        # map_data = cv2.addWeighted(x_scale_abs, 0.5, y_scale_abs, 0.5, 0)
    elif filter_type == 'laplacian':
        map_data = cv2.Laplacian(map_data.astype(np.uint8),ksize)
        map_data =  cv2.convertScaleAbs(map_data)
    else:
        raise ValueError('Not support filter type '+filter_type+'.')
    # elif filter_type == 'sobel':
    #     map_data = cv2.Sobel(map_data.astype(np.uint8),ksize)
    # max_value, min_value = np.max(map_data), np.min(map_data)
    # map_data = (map_data - min_value)*100.0/(max_value - min_value)
    map_data[map_data>0] = 100
    # print(max_value,min_value)
    # print(np.max(map_data), np.min(map_data)) 
    return map_data.astype(np.int8)


def bresenham_line_search(map_data,start, end):
    x1, y1 = start
    x2, y2 = end
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    s1 = 1 if ((x2 - x1) > 0) else -1
    s2 = 1 if ((y2 - y1) > 0) else -1
    boolinter_change = False
    if dy > dx:
        dx, dy = dy, dx
        boolinter_change = True
    e = 2 * dy - dx
    x = x1
    y = y1
    for i in range(0, int(dx + 1)):
        try:
            map_value = (map_data[y][x]+256) % 256
        except:
            # print('warning: searching out of the map range.')
            return (0, -1)
        if map_value >50 and map_value<255:
            return (map_value, np.linalg.norm(np.array([x, y])-start))
        if e >= 0:
            if boolinter_change:
                x += s1
            else:
                y += s2
            e -= 2 * dx
        if boolinter_change:
            y += s2
        else:
            x += s1
        e += 2 * dy
    return (0,-1)

if __name__ == '__main__':
    map = np.zeros((480,640),dtype=np.int8)
    draw_point(map,(50,50),5,100)
    points=[(50,50),(100,100),(50,100),(100,50)]
    print(np.array(points))
    draw_polygon(map,points,100,True)
    cv2.imshow("sadf",map)
    cv2.waitKey(0)

