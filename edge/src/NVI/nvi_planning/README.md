# nvi_planning

A ROS package for planning in navigation for visually impaired person application. 

This package consists of two main modules: [global_planning](./global_planning.md) and [local_planning](./local_planning.md). For more information (installation and usage in detail) about these modules, you can refer to their description documents. Note that the `local_path_searching_node` and `local_path_following_node` are two parts of local_planning_node. When using the wireless scheme, the `local_path_searching_node` should be launched on the server side while the `local_path_following_node` in the edge side.  

## Table of Contents

- [Usage](#Usage)
    - [Compile](#Compile)
    - [Run](#Run)
- [Author](#Author)
- [License](#license)


## Usage

Firstly install this package and move it to your workspace. Secondly, check the description documents for [global_planning](./global_planning.md) and [local_planning](./local_planning.md), make all environment requirements ready.

### Compile

compile this package in your workspace
```bash
catkin_make
```

### Run

run the launch file to run this package node
```bash
roslaunch nvi_planning nvi_planning.launch 
```

## Author

- Name: Lixuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn


## License
This package is released under GPLv3 as part of this repository. See the
repository root `README.md` license section and `LICENSE` for third-party
notices.
