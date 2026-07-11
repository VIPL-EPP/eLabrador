# Overview

This node subscribes to RGB-D and VIO (Visual-Inertial Odometry) topics. It performs semantic segmentation on the RGB images, projects the segmented data into a point cloud using the depth data and camera intrinsics, aligns the point cloud to the world coordinate system using VIO state estimation, and finally inserts it into a global OctoMap for publishing.

This node is modified based on the [Semantic Slam](https://github.com/floatlazer/semantic_slam) codebase. If you have any questions or need more foundational details, please refer to the [readme of the original repo](./README_original_repo.md).

# Installation & Environment Setup

## Dependencies

If you are using Conda to manage your environment, you need to manually install the ROS-related packages for the Python interpreter inside your virtual environment:

```sh
conda install python-orocos-kdl -c conda-forge
pip install rospkg catkin_pkg rospy catkin_tools empy==3.3.4
```

Install the required Python dependencies:

```sh
pip install -r semantic_slam/semantic_cloud/requeriments.txt
```

You will also need to use `rosdep` to automatically install other required system and ROS dependencies.

```sh
rosdep install --from-paths src --ignore-src -r -y
```

# Parameter Configuration

Please refer to the YAML files located in `src/semantic_slam/semantic_slam/params/` for parameter configurations.
