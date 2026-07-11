# nvi_visualize

English | [简体中文](./README.zh-CN.md)

## Environment

```sh
pip install pyproj folium
```

## Plot a GPS Trajectory from a Bag

```sh
rosrun nvi_visualize gps_plot.py --bag_path input.bag --gps_topic /ublox_driver/receiver_lla --output_path output.html
```

## Show a Live GPS Trajectory

Update `gps_topics` in `path_visualize.launch`, then run:

```sh
roslaunch nvi_visualize path_visualize.launch
```
