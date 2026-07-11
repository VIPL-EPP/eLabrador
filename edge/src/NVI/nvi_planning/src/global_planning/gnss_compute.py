import math
import numpy as np
from geographiclib.geodesic import Geodesic

'''
goegraphy format: 
point: (latitude, longitude)
'''

def get_p2pdistance(p1,p2):
    '''
    return the distance between two points on earth surface.
    '''
    geo_sol= Geodesic.WGS84.Inverse(p1[0],p1[1],p2[0],p2[1])
    return geo_sol['s12']

def get_p2pazimuth(p1,p2):
    '''
    return the azimuth of the line at point1, relative the north direction.
    '''
    geo_sol= Geodesic.WGS84.Inverse(p1[0],p1[1],p2[0],p2[1])
    return geo_sol['azi1']

def get_p2pgeodesic(p1,p2):
    '''
    return the azimuth of the line at point1, relative the north direction.
    '''
    geo_sol= Geodesic.WGS84.Inverse(p1[0],p1[1],p2[0],p2[1])
    return geo_sol['s12'],geo_sol['azi1']

def get_p2ldistance(point,line):
    '''
    return the distance from one point to given line on earth surface.

    Parameters:
    point: (lat, lon)
    line: [point1, point2]
    '''
    p0 = np.array([point[0],point[1]])
    p1 = np.array([line[0][0],line[0][1]])
    p2 = np.array([line[1][0],line[1][1]])
    geo_solp1p2 = Geodesic.WGS84.Inverse(p1[0],p1[1],p2[0],p2[1])
    geo_solp1p0 = Geodesic.WGS84.Inverse(p1[0],p1[1],p0[0],p0[1])
   
    return geo_solp1p0['s12']*abs(math.sin(math.radians(geo_solp1p0['azi1']-geo_solp1p2['azi1'])))
    


if __name__ == '__main__':
    p0 = (39.984275,116.32474)
    p1 = (39.983659,116.324774)
    # p1 = (39.983685,116.325703)
    p2 = (39.985477,116.324679)
    # geodict = Geodesic.WGS84.Inverse(p1[0],p1[1],p2[0],p2[1])
    print(get_p2pdistance(p1,p2))
    print(get_p2ldistance(p0,[p1,p2]))