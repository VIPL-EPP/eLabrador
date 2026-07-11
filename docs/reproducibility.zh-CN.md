# 复现边界

[English](./reproducibility.md) | 简体中文

本仓库是 eLabrador 的公开研究和工程发布，不是论文中所有物理实验的一键复现包。

## 直接提供

- 端侧 ROS 源码和 launch 文件
- 云侧语义服务源码和 Docker 部署文件
- 用于手机 GPS 和磁力计/方向转发的 Android APK
- 配置示例
- package 级 README 文件

## 用户需要自行提供

用户需要自行准备：

- API Key 和兼容模型服务凭据
- 高德/AMap Web 服务 Key
- 本地路线文件和实验场地配置
- 云侧 Mask2Former checkpoint、可选 Qwen-VL 权重和端侧本地模型权重
- 数据集、地图和 rosbag 文件
- RealSense、手机、腰带、麦克风和扬声器
- 只有在自行接入外部定位驱动时，才需要外部 GNSS/RTK 硬件和凭据；见 [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md)

## 建议复现层级

| 层级 | 目标 | 要求 |
| --- | --- | --- |
| 代码阅读 | 理解系统模块和论文实现 | 仓库本身 |
| 端侧构建 | 编译 ROS package | Ubuntu 20.04、ROS Noetic、依赖 |
| 传感器测试 | 运行 RealSense/手机 GPS/腰带节点 | 实物设备和本地配置 |
| 云侧测试 | 启动语义服务 | GPU 服务器、Mask2Former checkpoint、云侧 `.env` |
| 完整导航实验 | 复现集成室外导航流程 | 硬件、路线配置、凭据、云侧和端侧模型权重、本地环境调试 |

## 说明

物理导航行为受硬件安装、标定、光照、手机 GPS 质量、云服务可用性、手机前台运行状态、腰带连接、本地路线和模型版本影响。如果另行接入外部 GNSS/RTK 接收机，其信号质量和差分服务也会影响结果。
