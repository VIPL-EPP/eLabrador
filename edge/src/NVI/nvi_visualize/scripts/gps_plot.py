import folium
import math
import rosbag
from sensor_msgs.msg import NavSatFix
import argparse

def wgs84_to_gcj02(lat, lon):
    if out_of_china(lat, lon):
        return lat, lon
    dlat = transform_lat(lon - 105.0, lat - 35.0)
    dlon = transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglon = lon + dlon
    return mglat, mglon

def out_of_china(lat, lon):
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret

def transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret

a = 6378245.0
ee = 0.00669342162296594323

def extract_gps_from_bag(bag_path, topic_name):
    gps_coords = []
    with rosbag.Bag(bag_path, 'r') as bag:
        for topic, msg, t in bag.read_messages(topics=[topic_name]):
            gps_coords.append((msg.latitude, msg.longitude))
    return gps_coords

def plot_gps_coordinates_on_map(gps_coords, map_output_path='gps_map.html'):
    # 将WGS84坐标转换为GCJ-02坐标
    gcj02_coords = [wgs84_to_gcj02(lat, lon) for lat, lon in gps_coords]
    
    start_coords = gcj02_coords[0] if gcj02_coords else (0, 0)

    m = folium.Map(location=start_coords,
                       zoom_start=15,
                       control_scale=True,
                       control=False,
                       tiles=None
                       )

    folium.TileLayer(tiles='http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
                        attr="&copy; <a href=http://ditu.amap.com/>高德地图</a>",
                        min_zoom=0,
                        max_zoom=19,
                        control=True,
                        show=True,
                        overlay=False,
                        name='baseLayer',
                        ).add_to(m)
    # m = folium.Map(location=start_coords, zoom_start=15, tiles=None)
    
    # folium.TileLayer(
    #     tiles='https://webrd02.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}',
    #     attr='高德地图',
    #     name='高德地图'
    # ).add_to(m)
    
    folium.PolyLine(gcj02_coords, color="blue", weight=2.5, opacity=1).add_to(m)
    
    m.save(map_output_path)
    print(f"Map saved to {map_output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bag_path', type=str, required=True)
    parser.add_argument('--gps_topic', type=str, required=True)
    parser.add_argument('--output_path', type=str, default='gps_map.html')
    args = parser.parse_args()
    bag_path = args.bag_path
    gps_topic = args.gps_topic
    gps_coords = extract_gps_from_bag(bag_path, gps_topic)
    plot_gps_coordinates_on_map(gps_coords, args.output_path)
