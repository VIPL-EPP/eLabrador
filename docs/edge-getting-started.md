# Edge Getting Started

English | [简体中文](./edge-getting-started.zh-CN.md)

This is the recommended first document for running the eLabrador software stack. The main public software entry point is the edge-side ROS workspace at [`edge/`](../edge/).

The steps below assume the user is starting from a clean machine and wants to build the edge software, prepare local configuration, connect devices, and launch the system.

## Prerequisites

### Computing Device

| Item | Recommendation | Notes |
| --- | --- | --- |
| Edge computer | Native Ubuntu machine, preferably x86_64 laptop, mini PC, or NUC-class device | WSL and virtual machines are useful for reading code and limited rosbag playback, but hardware integration should use native Ubuntu. |
| USB | USB 3.0 port for the depth/RGB camera | RealSense devices are sensitive to USB bandwidth and cable quality. |
| Bluetooth | Bluetooth adapter for the vibration belt | Required when using the HC-05 belt. |
| Audio | Microphone and speaker or headset | Required for speech input/output modules. |
| Network | Internet access and access to the cloud semantic server address | Required for API services, dependency installation, Android phone GPS forwarding, and semantic mapping. |
| GPU (optional) | NVIDIA GPU | Useful for local deep-learning inference. Cloud-side semantic inference can reduce edge GPU requirements. |

### Software Dependencies

| Item | Requirement |
| --- | --- |
| Operating system | Ubuntu 20.04 native installation |
| ROS | ROS Noetic desktop |
| Build tools | `git`, `build-essential`, `cmake`, `catkin_make` |
| Python | Python 3, `pip3`, edge Python packages from [`edge/setup/requirements.txt`](../edge/setup/requirements.txt) |
| Camera stack | Intel RealSense SDK and ROS wrapper for the target machine |
| Localization stack | Ceres/VINS-Mono dependencies, Eigen, SuiteSparse, glog, gflags |
| Device stack | Bluetooth, BlueZ, serial, udev, audio, and speech packages |
| Deep-learning stack | Edge-side PyTorch/OCR/local-planning packages as needed. Mask2Former runtime dependencies are prepared on the cloud semantic server; Qwen-VL is optional if explicitly enabled there. |

### Sensors and Peripherals

| Device | Expected Use |
| --- | --- |
| Intel RealSense D455 or compatible RGB-D camera | Visual perception, depth input, and sensor stack testing |
| Android phone GPS app from [`mobile/android/`](../mobile/android/) | Default outdoor positioning input |
| HC-05 Bluetooth vibration belt | Wearable navigation feedback |
| Microphone and speaker/headset | Voice command and audio feedback |
| External GNSS/RTK device (optional, not bundled) | High-precision outdoor positioning input; see [RTK/GNSS Extensions](./rtk-gnss-extensions.md) |

### Accounts and Services

| Service | Purpose |
| --- | --- |
| AMap/Gaode API key | Walking route planning |
| DashScope API key | Speech recognition service used by existing modules |
| OpenAI-compatible multimodal/VQA endpoint | Vision-language or VQA module integration |
| Cloud semantic server | Mask2Former semantic inference service. Configure it before running semantic mapping or the basic whole-system stack. See [Cloud Semantic Server](./cloud-semantic-server.md). |

### Local Files and Assets

The public repository does not include private credentials, real route files, experiment-site configuration, model weights, datasets, or rosbag captures. Prepare these locally:

| Asset | Local Preparation |
| --- | --- |
| Environment variables | Copy [`.env.example`](../.env.example) to `.env` and fill in local values. |
| Route and key-message files | Copy [`key_msg.example.json`](../edge/src/NVI/nvi_management/config/key_msg.example.json) and [`route_config.example.json`](../edge/src/NVI/nvi_management/config/route_config.example.json) to local non-example files. |
| Edge-side model weights | Download the RSSM local-planning checkpoint from [Google Drive](https://drive.google.com/file/d/1mid3cVu4RZW96qWVOgOr6-XL6GBNSkLD/view), place it at `models/best_rssm_trajectory_model.pth`, or set `NVI_LOCAL_PLANNING_MODEL` to the directory that contains that file. Place any enabled edge-side OCR/traffic-light weights under a local `models/` directory or configure their paths in `.env`. Mask2Former checkpoints are prepared in the cloud semantic server, not on the default edge path. |
| Runtime data | Keep datasets, rosbag files, maps, logs, and outputs under ignored local directories such as `data/`, `logs/`, and `outputs/`. |

## Install System Dependencies

Install ROS Noetic desktop for Ubuntu 20.04 first, then install the base tools:

```bash
sudo apt update
sudo apt install -y git build-essential cmake curl wget python3-pip
```

Install core ROS and system packages:

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

Install Ceres/VINS-Mono dependencies:

```bash
sudo apt install -y libgoogle-glog-dev libgflags-dev libatlas-base-dev libeigen3-dev libsuitesparse-dev
```

If VINS-Mono requires Ceres Solver 1.14.x in your environment:

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

## Install Edge Python Dependencies

Edge-side helper files are stored in [`edge/setup/`](../edge/setup/).

```bash
pip3 install -r edge/setup/requirements.txt
pip3 install ./edge/setup/nvi_octomap
```

Edge-side deep-learning packages such as PyTorch, PaddlePaddle, TensorFlow, OCR, and local-planning dependencies are hardware and CUDA dependent. Install versions that match the target machine. Prepare Mask2Former dependencies on the cloud semantic server; see [Cloud Semantic Server](./cloud-semantic-server.md).

## Prepare Local Configuration

Copy the root environment template:

```bash
cp .env.example .env
```

Fill in the .env file according to the actual situation and load it before running:

```bash
set -a
source .env
set +a
```

Copy route and key-message templates before running management nodes:

```bash
cp edge/src/NVI/nvi_management/config/key_msg.example.json edge/src/NVI/nvi_management/config/key_msg.json
cp edge/src/NVI/nvi_management/config/route_config.example.json edge/src/NVI/nvi_management/config/route_config.json
```

Edit the local copies for your machine, experiment site, route points, API keys, model paths, device aliases, belt MAC address, and cloud semantic endpoints. For more detail, see [Configuration](./configuration.md).

## Connect and Check Devices(reference)

Check RealSense:

```bash
realsense-viewer
roslaunch nvi_bringup nvi_realsense.launch
```

Check ROS visibility:

```bash
rosnode list
rostopic list
```

Check the belt serial alias after applying local udev rules:

```bash
ls /dev/ttyBelt
```

Check Bluetooth belt discovery:

```bash
bluetoothctl devices
```

## Build Edge Workspace

```bash
source /opt/ros/noetic/setup.bash
cd edge
catkin_make
source devel/setup.bash
```

If the machine is resource constrained:

```bash
catkin_make -j1
```

## First Launch

Start with the sensor-only stack:

```bash
roslaunch nvi_bringup nvi_sensor.launch
```

Then launch the basic whole-system stack. This stack includes semantic mapping, so configure `MASK2FORMER_HTTP_URL` and prepare the cloud semantic server before running it. `MASK2FORMER_WS_URI` is only for the non-default WebSocket detector path:

```bash
set -a
source .env
set +a

roslaunch nvi_bringup nvi.launch
```
or directly using
```bash
./run_nvi.sh
```

Additional launch entry points:

| Launch file | Purpose |
| --- | --- |
| `nvi_realsense.launch` | RealSense camera |
| `nvi_phone_gps.launch` | Android phone GPS bridge |
| `nvi_planning.launch` | Global/local planning |
| `nvi_belt.launch` | Vibration belt test |
| `nvi_semantic_cloud.launch` | Edge-side semantic cloud client |
| `blind_dreamer.launch` | Outdoor navigation experiment stack |

Outdoor navigation experiment example:

```bash
roslaunch nvi_bringup blind_dreamer.launch record_path:=test.bag
```

Belt topic test:

```bash
rostopic pub /local_planning/belt std_msgs/String "data: '001'"
```

## Next Documents

- [Configuration](./configuration.md): environment variables, model paths, route files, device aliases, and private local assets
- [Cloud Semantic Server](./cloud-semantic-server.md): cloud semantic service for semantic mapping and Docker deployment
- [Mobile Android](./mobile-android.md): Android GPS and magnetometer/orientation forwarding apps
- [RTK/GNSS Extensions](./rtk-gnss-extensions.md): external high-precision positioning integration references
- [Reproducibility](./reproducibility.md): public reproduction boundary
