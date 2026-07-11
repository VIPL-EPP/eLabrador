# 整体说明

该节点的功能是订阅rgbd+vio话题，使用rgb图像进行语义分割，然后通过depth数据和相机内参映射为点云，再通过vio对齐到世界坐标系，最后插入全局octomap中并发布。

本节点基于[Semantic Slam](https://github.com/floatlazer/semantic_slam)的代码进行修改，如有疑问可以阅读[readme of original repo](./README_original_repo.md)。

# 安装环境

## 依赖包

如果使用conda管理环境，需要给虚拟环境内的python手动安装ros相关包

```
conda install python-orocos-kdl -c conda-forge
pip install rospkg catkin_pkg rospy catkin_tools empy==3.3.4
```

安装python依赖包

```
pip install -r semantic_slam/semantic_cloud/requeriments.txt
```

需要额外使用rosdep自动安装其他所需功能。

```
rosdep install --from-paths src --ignore-src -r -y
```

# 参数配置

请查看 `src/semantic_slam/semantic_slam/params/` 下的yaml文件。
