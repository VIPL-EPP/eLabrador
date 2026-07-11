# Semantic OctoMap Mapping Node

## Overview
This ROS node is designed for real-time semantic 3D mapping. It subscribes to RGB-D and VIO (Visual-Inertial Odometry) topics, performs semantic segmentation on the incoming RGB images, and projects the segmented pixels into 3D point clouds using the corresponding depth data and camera intrinsic parameters. These semantic point clouds are then aligned to the world coordinate system using the VIO state estimation, and finally integrated into a global OctoMap and published.

This repository is modified based on the original [Semantic Slam](https://github.com/floatlazer/semantic_slam) project. For more foundational details, please refer to the [original repository's README](./README_original_repo.md).

---

## Installation & Environment Setup

### 1. ROS Python Dependencies (Conda Environment)
If you use `conda` to manage your virtual environments, you need to manually install the ROS-related Python packages into your active conda environment:

```sh
conda install python-orocos-kdl -c conda-forge
pip install rospkg catkin_pkg rospy catkin_tools empy==3.3.4
```

### 2. Python Package Dependencies

Install the required Python dependencies by running:

```sh
pip install -r semantic_slam/semantic_cloud/requeriments.txt
```

### 3. ROS Dependencies

Use `rosdep` to automatically resolve and install other system and ROS dependencies required by this package:

```sh
rosdep install semantic_slam
```

---

## Parameter Configuration

All configurable parameters (such as topic names, thresholds, and camera settings) are detailed with inline comments in the YAML files. You can review and modify them under the following directory:

```text
src/semantic_slam/semantic_slam/params/
```
