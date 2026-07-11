# 端侧入门

[English](./edge-getting-started.md) | 简体中文

这是运行 eLabrador 软件栈的推荐第一入口。主要公开软件入口是端侧 ROS 工作空间 [`edge/`](../edge/)。

下面的步骤假设用户从一台干净机器开始，需要构建端侧软件、准备本地配置、接入设备并启动系统。

## 前置条件

### 计算设备

| 项目 | 建议 | 说明 |
| --- | --- | --- |
| 端侧计算机 | 原生 Ubuntu 机器，建议 x86_64 笔记本、迷你主机或 NUC 级设备 | WSL 和虚拟机适合阅读代码和有限的 rosbag 回放，但实物硬件接入建议使用原生 Ubuntu。 |
| USB | 面向 RGB-D 相机的 USB 3.0 接口 | RealSense 对 USB 带宽和线缆质量比较敏感。 |
| 蓝牙 | 面向震动腰带的蓝牙适配器 | 使用 HC-05 腰带时需要。 |
| 音频 | 麦克风和扬声器或耳机 | 语音输入/输出模块需要。 |
| 网络 | 可访问互联网，并能访问云侧语义服务器地址 | API 服务、依赖安装、Android 手机 GPS 转发和语义建图需要网络。 |
| GPU（可选） | NVIDIA GPU | 本地深度学习推理会受益于 GPU；如果使用云侧语义推理，端侧 GPU 要求可降低。 |

### 软件依赖

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Ubuntu 20.04 原生安装 |
| ROS | ROS Noetic desktop |
| 构建工具 | `git`、`build-essential`、`cmake`、`catkin_make` |
| Python | Python 3、`pip3`、[`edge/setup/requirements.txt`](../edge/setup/requirements.txt) 中的端侧 Python 包 |
| 相机栈 | 适配目标机器的 Intel RealSense SDK 和 ROS wrapper |
| 定位栈 | Ceres/VINS-Mono 依赖、Eigen、SuiteSparse、glog、gflags |
| 设备栈 | Bluetooth、BlueZ、serial、udev、audio、speech 相关包 |
| 深度学习栈 | 按需安装端侧 PyTorch/OCR/局部规划相关依赖。Mask2Former 运行依赖在云侧语义服务中准备；Qwen-VL 只有在云侧显式启用时才需要。 |

### 传感器与外设

| 设备 | 用途 |
| --- | --- |
| Intel RealSense D455 或兼容 RGB-D 相机 | 视觉感知、深度输入和传感器栈测试 |
| [`mobile/android/`](../mobile/android/) 中的 Android 手机 GPS 应用 | 默认室外定位输入 |
| HC-05 蓝牙震动腰带 | 穿戴式导航反馈 |
| 麦克风和扬声器/耳机 | 语音指令和音频反馈 |
| 外部 GNSS/RTK 设备（可选，不随仓库内置） | 高精度室外定位输入；见 [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md) |

### 账号与服务

| 服务 | 用途 |
| --- | --- |
| 高德/AMap API Key | 步行路线规划 |
| DashScope API Key | 现有模块使用的语音识别服务 |
| OpenAI-compatible 多模态/VQA endpoint | 视觉语言或 VQA 模块接入 |
| 云侧语义服务 | Mask2Former 语义推理服务。运行语义建图或基础整机栈前需要配置。见 [云侧语义服务](./cloud-semantic-server.zh-CN.md)。 |

### 本地文件与资产

公开仓库不包含私有凭据、真实路线文件、实验场地配置、模型权重、数据集或 rosbag 采集文件。请在本地准备：

| 资产 | 本地准备 |
| --- | --- |
| 环境变量 | 复制 [`.env.example`](../.env.example) 为 `.env` 并填写本地值。 |
| 路线和关键消息文件 | 复制 [`key_msg.example.json`](../edge/src/NVI/nvi_management/config/key_msg.example.json) 和 [`route_config.example.json`](../edge/src/NVI/nvi_management/config/route_config.example.json) 为本地非 example 文件。 |
| 端侧模型权重 | 从 [Google Drive](https://drive.google.com/file/d/1mid3cVu4RZW96qWVOgOr6-XL6GBNSkLD/view) 下载 RSSM 局部规划 checkpoint，将其放在 `models/best_rssm_trajectory_model.pth`，或将 `NVI_LOCAL_PLANNING_MODEL` 设置为包含该文件的目录。按需启用的端侧 OCR/交通灯等权重可放在本地 `models/` 目录下，或在 `.env` 中配置路径。Mask2Former checkpoint 在云侧语义服务中准备，不属于默认 edge 本地路径。 |
| 运行数据 | 数据集、rosbag、地图、日志和输出建议放在 `data/`、`logs/`、`outputs/` 等被忽略的本地目录中。 |

## 安装系统依赖

先为 Ubuntu 20.04 安装 ROS Noetic desktop，然后安装基础工具：

```bash
sudo apt update
sudo apt install -y git build-essential cmake curl wget python3-pip
```

安装核心 ROS 和系统包：

```bash
sudo apt install -y \
  ros-noetic-serial \
  ros-noetic-pcl-conversions \
  ros-noetic-pcl-msgs \
  ros-noetic-pcl-ros \
  ros-noetic-tf2-eigen \
  ros-noetic-octomap \
  ros-noetic-octomap-msgs \
  ros-noetic-octomap-rviz-plugins \
  ros-noetic-nmea-msgs \
  libudev-dev \
  libglib2.0-dev \
  libbluetooth-dev \
  bluetooth \
  bluez \
  python-bluez \
  portaudio19-dev \
  espeak
```

安装 Ceres/VINS-Mono 依赖：

```bash
sudo apt install -y libgoogle-glog-dev libgflags-dev libatlas-base-dev libeigen3-dev libsuitesparse-dev
```

如果当前环境中的 VINS-Mono 需要 Ceres Solver 1.14.x：

```bash
git clone https://gitlab.com/NikolausDemmel/ceres-solver.git
cd ceres-solver
git checkout dc8ef467e3bf33549373e128c864589e86d7b0b4
mkdir build
cd build
cmake ..
make -j3
sudo make install
```

## 安装端侧 Python 依赖

端侧辅助文件位于 [`edge/setup/`](../edge/setup/)。

```bash
pip3 install -r edge/setup/requirements.txt
pip3 install ./edge/setup/nvi_octomap
```

端侧 PyTorch、PaddlePaddle、TensorFlow、OCR、局部规划等深度学习依赖与硬件和 CUDA 版本相关，请安装与目标机器匹配的版本。Mask2Former 依赖在云侧语义服务中准备，见 [云侧语义服务](./cloud-semantic-server.zh-CN.md)。

## 准备本地配置

复制根目录环境变量模板：

```bash
cp .env.example .env
```

根据实际情况填写 .env 文件并在运行前加载：

```bash
set -a
source .env
set +a
```

运行 management 节点前复制路线和关键消息模板：

```bash
cp edge/src/NVI/nvi_management/config/key_msg.example.json edge/src/NVI/nvi_management/config/key_msg.json
cp edge/src/NVI/nvi_management/config/route_config.example.json edge/src/NVI/nvi_management/config/route_config.json
```

根据本机、实验场地、路线点、API Key、模型路径、设备别名、腰带 MAC 地址和云侧语义端点编辑本地副本。更多说明见 [配置](./configuration.zh-CN.md)。

## 接入并检查设备（供参考，以实际采用的外设装备为准）

检查 RealSense：

```bash
realsense-viewer
roslaunch nvi_bringup nvi_realsense.launch
```

检查 ROS 可见性：

```bash
rosnode list
rostopic list
```

应用本地 udev 规则后检查腰带串口别名：

```bash
ls /dev/ttyBelt
```

检查蓝牙腰带发现情况：

```bash
bluetoothctl devices
```

## 构建端侧工作空间

```bash
source /opt/ros/noetic/setup.bash
cd edge
catkin_make
source devel/setup.bash
```

如果机器资源有限：

```bash
catkin_make -j1
```

## 首次启动

先启动传感器栈：

```bash
roslaunch nvi_bringup nvi_sensor.launch
```

再启动基础整机栈。该栈包含语义建图，运行前需要配置 `MASK2FORMER_HTTP_URL`，并准备好云侧语义服务。`MASK2FORMER_WS_URI` 仅用于非默认 WebSocket detector 路径：

```bash
set -a
source .env
set +a

roslaunch nvi_bringup nvi.launch
```
或直接使用提供的启动脚本

```bash
./run_nvi.sh
```

其他启动入口：

| 启动文件 | 用途 |
| --- | --- |
| `nvi_realsense.launch` | RealSense 相机 |
| `nvi_phone_gps.launch` | Android 手机 GPS 桥接 |
| `nvi_planning.launch` | 全局/局部规划 |
| `nvi_belt.launch` | 震动腰带测试 |
| `nvi_semantic_cloud.launch` | 端侧云语义客户端 |
| `blind_dreamer.launch` | 室外导航实验栈 |

室外导航实验示例：

```bash
roslaunch nvi_bringup blind_dreamer.launch record_path:=test.bag
```

腰带 topic 测试：

```bash
rostopic pub /local_planning/belt std_msgs/String "data: '001'"
```

## 后续文档

- [配置](./configuration.zh-CN.md)：环境变量、模型路径、路线文件、设备别名和私有本地资产
- [云侧语义服务](./cloud-semantic-server.zh-CN.md)：语义建图使用的云侧语义服务和 Docker 部署
- [Android 移动端](./mobile-android.zh-CN.md)：Android GPS 和磁力计/方向数据转发应用
- [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md)：外部高精度定位接入参考
- [复现边界](./reproducibility.zh-CN.md)：公开复现边界
