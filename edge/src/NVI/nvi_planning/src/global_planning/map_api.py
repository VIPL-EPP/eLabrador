import os
import requests


def _get_amap_key():
    key = os.environ.get("AMAP_API_KEY", "").strip()
    if not key:
        raise RuntimeError("AMAP_API_KEY is required for global planning. Apply for an AMap key and export it before launching this node.")
    return key

def _gpstr2float(gps: str):
    longitude, latitude = gps.split(",")
    longitude, latitude = float(longitude), float(latitude)
    return latitude, longitude


def location2GPS(location: str):
    key = _get_amap_key()
    url = "https://restapi.amap.com/v3/geocode/geo?address=%s&output=json&key=%s" % (
        location, key)
    res = requests.get(url, timeout=10).json()
    # TODO: Handle the case where the address lookup returns no result.
    # print(res)
    # print("Requested location: %s" % location)
    if res["count"] == "1":
        print("Resolved address: %s" % res["geocodes"][0]["formatted_address"])
        GPS = res["geocodes"][0]["location"]
        # "116.221122, 39.112211"
        return _gpstr2float(GPS)
    else:
        print("%s results returned" % res["count"])


def beginEnd2waypoints(begin, end):
    key = _get_amap_key()
    origion = str(begin[1]) + "," + str(begin[0])
    destination = str(end[1]) + "," + str(end[0])
    url = "https://restapi.amap.com/v3/direction/walking?origin=%s&destination=%s&output=json&key=%s" \
          % (origion, destination, key)
    res = requests.get(url, timeout=10).json()
    if res['info'] == 'ok':
        return res["route"]["paths"][0]["steps"]
    else:
        raise ValueError('Invalid input. Info: %s'%res['info'])
