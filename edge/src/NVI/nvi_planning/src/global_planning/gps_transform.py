import math
# math.pi = 3.14159265358979324
# _Xmath.pi: 3.14159265358979324 * 3000.0 / 180.0
_A = 6378245.0 # a: projection factor used when mapping the ellipsoid to a planar map frame
_EE = 0.00669342162296594323 # ee: eccentricity of the reference ellipsoid

def _transformLat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret

def _transformLon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret

def _delta(lat, lon):
    # a = 6378245.0 # a: projection factor used when mapping the ellipsoid to a planar map frame。
    # ee = 0.00669342162296594323 # ee: eccentricity of the reference ellipsoid。
    dLat = _transformLat(lon - 105.0, lat - 35.0)
    dLon = _transformLon(lon - 105.0, lat - 35.0)
    radLat = lat / 180.0 * math.pi
    magic = math.sin(radLat)
    magic = 1 - _EE * magic * magic
    sqrtMagic = math.sqrt(magic)
    dLat = (dLat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtMagic) * math.pi)
    dLon = (dLon * 180.0) / (_A / sqrtMagic * math.cos(radLat) * math.pi)
    return { 'lat': dLat, 'lon': dLon }


def wgs842gcj02(wgs_lat,wgs_lon):
    d = _delta(wgs_lat, wgs_lon)
    return { 'lat': wgs_lat + d['lat'], 'lon': wgs_lon + d['lon'] }
