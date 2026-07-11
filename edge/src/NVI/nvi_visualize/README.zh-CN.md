# 使用方法

[English](./README.md) | 简体中文

## 环境

```sh
pip install pyproj folium
```

## 在地图上绘制 bag 中的 GPS 轨迹

```sh
rosrun nvi_visualize gps_plot.py --bag_path input.bag --gps_topic /ublox_driver/receiver_lla --output_path output.html
```

## 实时显示 GPS 轨迹

在 `path_visualize.launch` 文件中修改 `gps_topics` 后运行：

```sh
roslaunch nvi_visualize path_visualize.launch
```
