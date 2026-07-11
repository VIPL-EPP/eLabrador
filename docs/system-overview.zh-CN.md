# 系统总览

[English](./system-overview.md) | 简体中文

eLabrador 按穿戴式导航系统的部署组成组织为三个公开部分：

| 模块 | 路径 | 作用 |
| --- | --- | --- |
| 端侧 | [`edge/`](../edge/) | 运行传感器、定位、规划、语音、OCR、腰带反馈和整机 launch 的 ROS 1 catkin 工作空间 |
| 云侧 | [`cloud/`](../cloud/) | 端侧模块使用的语义感知服务；当前公开入口为 [`cloud/semantic-server/`](../cloud/semantic-server/) |
| 移动端 | [`mobile/`](../mobile/) | 用于手机 GPS 和磁力计/方向数据转发的 Android 辅助应用；APK 位于 [`mobile/android/`](../mobile/android/) |

## 端侧模块

核心端侧 package 位于 [`edge/src/NVI/`](../edge/src/NVI/)。

| Package | 功能 |
| --- | --- |
| `nvi_bringup` | 整机启动文件、传感器启动文件、实验启动文件 |
| `nvi_msgs` | 共享自定义 ROS 消息 |
| `nvi_management` | 任务管理、路线配置、命令路由 |
| `nvi_planning` | 全局规划、局部规划、路径搜索、路径跟随 |
| `semantic_slam` | 语义点云与 OctoMap 集成 |
| `nvi_vio/VINS-Mono` | 视觉惯性里程计 |
| `rtk` | Android 手机 GPS 桥接；外部 RTK/GNSS 驱动不随默认仓库内置 |
| `nvi_speech` | 语音识别和命令解析 |
| `nvi_voice` | 语音提示 |
| `nvi_belt` | 震动腰带通信 |
| `nvi_ocr` | OCR 节点和配置 |
| `nvi_visualize` | GPS 和路径可视化 |

## 运行时数据流

运行时，[`edge/`](../edge/) 是串联系统的 ROS 图。移动端应用和本地设备先把传感器数据送入端侧栈；默认云侧语义路径是端侧 Mask2Former HTTP 客户端，通过 `MASK2FORMER_HTTP_URL` 配置连接地址。

```text
输入层
  RealSense RGB-D + IMU
  来自 mobile/android/ 的 Android GPS 和方向数据
  麦克风、本地路线文件和设备配置
        |
        v
edge/ ROS 图
  1. 传感器驱动和桥接节点发布相机、里程计、手机 GPS、
     方向、音频和设备状态 topic。
  2. VIO/定位与手机 GPS 模块估计位姿，并对齐室外坐标。
  3. 感知、OCR 和语义客户端生成场景线索；启用云侧推理时，
     语义帧会发送到 cloud/。
        |
        +--> cloud/semantic-server
        |      Mask2Former HTTP 端点
        |      显式启用时可接入 Qwen-VL 服务
        |      返回语义 mask 和标签
        |
        v
规划与管理
  全局路线 -> 局部代价地图/目标物 -> 局部路径/跟随指令
  任务管理负责路由用户命令、系统状态和 launch 级配置
        |
        v
反馈与记录
  nvi_voice 播放语音提示
  nvi_belt 发送震动模式
  可视化与 rosbag launch 文件记录选定 topic
```

## 主要启动入口

整机和实验启动文件位于 [`edge/src/NVI/nvi_bringup/launch/`](../edge/src/NVI/nvi_bringup/launch/)。

| 启动文件 | 用途 |
| --- | --- |
| `nvi.launch` | 基础整机栈，包含语义建图 |
| `blind_dreamer.launch` | 室外导航实验栈 |
| `nvi_sensor.launch` | 传感器栈 |
| `nvi_realsense.launch` | RealSense 相机 |
| `nvi_vio.launch` | VINS-Mono |
| `nvi_semantic.launch` | 语义建图 |
| `nvi_planning.launch` | 规划栈 |
| `nvi_phone_gps.launch` | Android 手机 GPS 桥接 |
| `nvi_ocr.launch` | OCR |
| `control_belt.launch` | 腰带控制实验 |

如需高精度定位，请另行接入外部 GNSS/RTK 驱动；见 [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md)。
