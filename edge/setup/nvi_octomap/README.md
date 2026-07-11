# nvi_octomap

A package for binding Python and OctoMap C++ library and realizing the required methods of navigation for visually impaired people project.

This package uses [pybind11](https://pybind11.readthedocs.io/en/stable/changelog.html) to bind Python and C++. 

## Table of Contents

- [Environment](#Environment)
- [Usage](#Usage)
    - [Install](#Install)
    - [Compile](#Compile)
    - [Test](#Test)
- [Author](#Author)
- [License](#license)

## Environment
- Linux
- Python3

## Usage

Firstly install this package and move it to your workspace.

### Install
1. You have to install the OctoMap C++ library. About how to install it, you can follow [OctoMap](https://octomap.github.io/). For quick installation, you can run:
```bash
sudo apt install ros-$ROS_DISTRO-octomap-ros 
sudo apt install ros-$ROS_DISTRO-octomap-msgs
sudo apt install ros-$ROS_DISTRO-octomap-server
sudo apt install ros-$ROS_DISTRO-octomap-rviz-plugins
```

2. Check if there is 'pybind11' folder in the root directory of this package. If not, install [pybind-cmake_example](https://github.com/pybind/cmake_example), and then follow its 'READEME.md' or just copy 'pybind11' folder to the root directory of this package.

### Compile
Before compiling this package, I strongly recommend selecting the Python environment you desired to use this package as the current Python environment.

compile this package in the parent directory
```bash
cd ..
pip install ./nvi_octomap
```
Then, you will find the compiled nvi_octomap package in your Python lib.

### Test

import the package, and check its attributes list.
```python
import nvi_octomap
dir(nvi_octomap)
```


## Author

- Name: Lixuan Zhang
- E-mail: lixuan.zhang@vipl.ict.ac.cn

This project exists thanks to the [pybind11](https://pybind11.readthedocs.io/en/stable/changelog.html) and   [OctoMap](https://octomap.github.io/) support.


## License
[MIT](LICENSE) © Richard Littauer