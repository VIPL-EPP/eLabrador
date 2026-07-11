# global_planning

 In this global planning module, the global planning is provided by [Gaode Map](https://lbs.amap.com/), we do some individuation work to make it compatible with our visually impaired person application system. Additionally, the global planning uses the [geographiclib](https://geographiclib.sourceforge.io/html/python/code.html#module-geographiclib.geodesic) for Python to compute the distance and azimuth between two points on the earth.


## Table of Contents

- [Environment](#Environment)
- [Usage](#Usage)
    - [Install](#Install)
    - [Compile](#Compile)
    - [Run](#Run)
    - [Test](#Test)
- [Author](#Author)
- [License](#license)

## Environment
- Linux
- ROS noetic
- Python3

## Usage

Firstly install this package and move it to your workspace.

### Install
Install the python requirements

```
pip install geographiclib
```

### Compile

compile this package in your workspace
```bash
catkin_make
```

### Run

run the launch file to run this package node
```bash
roslaunch nvi_planning global_planning.launch 
```
if there are some errors, running this command make give some help
```bash
chmod +x nvi_planning/scripts/global_planning_node.py
```

note that you can also use your Gaode API key by replacing the  _key in [map_api](./src/global_planning/map_api.py) module. For more information about Gaode API, you can refer to [Gaode Map](https://lbs.amap.com/).

### Test

This package requires GPS information in NavSatFix format. The default phone GPS bridge publishes `/phone_gps/receiver_lla` and remaps it to `/ublox_driver/receiver_lla` for compatibility. To use another positioning source, publish `NavSatFix` to `/ublox_driver/receiver_lla` or update the subscriber topic.

change the destination
```
rostopic pub /global_planning/destination std_msgs/String "中国科学院计算所"
```

note that the param in ./config/*.yaml can be modified to satisfy personal requirements. 

## Author

- Name: Lixuan Zhang, Boyuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn, boyuan.zhang@vipl.ict.ac.cn

This project exists thanks to the [Gaode Map](https://lbs.amap.com/) support.


## License
This package is released under GPLv3 as part of this repository. See the
repository root `README.md` license section and `LICENSE` for third-party
notices.
