# local_planning

In this local planning module, local planning is realized by an obstacle avoidance system.

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
- OpenCV
- nvi_octomap

## Usage

Firstly install this package and move it to your workspace.

### Install
Install the python requirements
```
pip install opencv-python==4.1.0.25 opencv-contrib-python==4.1.0.25 opencv-python-headless==4.1.0.25
```
note that this package is tested on OpenCV 4.1.0.25 and usually it is okay to install other OpenCV versions.

Install the nvi_octomap requirements. 

If the "nvi_octomap/" file folder can be found in your workspace, install it by pip. Otherwise, you can contact the author for a copy.
```bash
pip install ./nvi_octomap
``` 

### Compile

compile this package in your workspace
```bash
catkin_make
```

### Run

run the launch file to run this package node
```bash
roslaunch nvi_planning local_planning.launch 
```
if there are some errors, running this command make give some help
```bash
chmod +x nvi_planning/scripts/local_planning_node.py
```

### Test

This package requires local map information in Octomap format and local path information in Path format. To use this package you have to publish local map information in Octomap format to "/octomap_full" and local path in Path format to "/vins_estimator/path". Besides, you also can publish other topic address you appoint.

## Author

- Name: Lixuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn

## License
This package is released under GPLv3 as part of this repository. See the
repository root `README.md` license section and `LICENSE` for third-party
notices.
