# System Overview

English | [简体中文](./system-overview.zh-CN.md)

eLabrador is organized as a wearable navigation system with three public system areas:

| Area | Path | Role |
| --- | --- | --- |
| Edge | [`edge/`](../edge/) | ROS 1 catkin workspace running sensors, localization, planning, speech, OCR, belt feedback, and whole-system launch files |
| Cloud | [`cloud/`](../cloud/) | Semantic perception service used by edge-side modules; current public entry point is [`cloud/semantic-server/`](../cloud/semantic-server/) |
| Mobile | [`mobile/`](../mobile/) | Android helper apps for phone GPS and magnetometer/orientation forwarding; APKs are under [`mobile/android/`](../mobile/android/) |

## Edge Modules

Core edge packages live under [`edge/src/NVI/`](../edge/src/NVI/).

| Package | Purpose |
| --- | --- |
| `nvi_bringup` | Whole-system launch files, sensor launch files, experiment launch files |
| `nvi_msgs` | Shared custom ROS messages |
| `nvi_management` | Task management, route configuration, command routing |
| `nvi_planning` | Global planning, local planning, path search, path following |
| `semantic_slam` | Semantic point cloud and OctoMap integration |
| `nvi_vio/VINS-Mono` | Visual-inertial odometry |
| `rtk` | Android phone GPS bridge; external RTK/GNSS drivers are not bundled |
| `nvi_speech` | Speech recognition and command parsing |
| `nvi_voice` | Voice prompts |
| `nvi_belt` | Vibration belt communication |
| `nvi_ocr` | OCR node and configuration |
| `nvi_visualize` | GPS and path visualization |

## Runtime Data Flow

At runtime, [`edge/`](../edge/) is the ROS graph that ties the system together. Mobile apps and local devices feed sensor data into the edge stack; the default cloud semantic path is the edge-side Mask2Former HTTP client configured with `MASK2FORMER_HTTP_URL`.

```text
Input layer
  RealSense RGB-D + IMU
  Android GPS and orientation from mobile/android/
  microphone, local route files, and device configuration
        |
        v
edge/ ROS graph
  1. Sensor drivers and bridges publish camera, odometry, phone GPS,
     orientation, audio, and device-status topics.
  2. VIO/localization and phone GPS modules estimate pose and align
     outdoor coordinates.
  3. Perception, OCR, and semantic clients produce scene cues; semantic
     frames are sent to cloud/ when cloud inference is enabled.
        |
        +--> cloud/semantic-server
        |      Mask2Former HTTP endpoint
        |      optional Qwen-VL service if explicitly enabled
        |      returns semantic masks and labels
        |
        v
Planning and management
  global route -> local cost map/objects -> local path/following command
  task management routes user commands, system state, and launch-level config
        |
        v
Feedback and logging
  nvi_voice speaks prompts
  nvi_belt sends vibration patterns
  visualization and rosbag launch files record selected topics
```

## Main Launch Entry Points

Whole-system and experiment launch files are in [`edge/src/NVI/nvi_bringup/launch/`](../edge/src/NVI/nvi_bringup/launch/).

| Launch file | Purpose |
| --- | --- |
| `nvi.launch` | Basic whole-system stack, including semantic mapping |
| `blind_dreamer.launch` | Outdoor navigation experiment stack |
| `nvi_sensor.launch` | Sensor stack |
| `nvi_realsense.launch` | RealSense camera |
| `nvi_vio.launch` | VINS-Mono |
| `nvi_semantic.launch` | Semantic mapping |
| `nvi_planning.launch` | Planning stack |
| `nvi_phone_gps.launch` | Android phone GPS bridge |
| `nvi_ocr.launch` | OCR |
| `control_belt.launch` | Belt control experiment |

For high-precision positioning, integrate external GNSS/RTK drivers separately; see [RTK/GNSS Extensions](./rtk-gnss-extensions.md).
