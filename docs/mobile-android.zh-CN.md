# Android 移动端应用

[English](./mobile-android.md) | 简体中文

Android 辅助 APK 存放于 [`mobile/android/`](../mobile/android/)。这些 APK 用于把手机侧传感器数据转发给端侧 ROS 系统。

本仓库只提供 APK 产物，不提供 Android 源码工程。该模块的复现含义是：安装 APK，将其连接到端侧机器，并验证 ROS topic 能收到数据。

`SensaGram-v1.5.2.apk.1.1` 是来自第三方项目 [`UmerCodez/SensaGram`](https://github.com/UmerCodez/SensaGram) 的 SensaGram `v1.5.2` APK。该 APK 使用 GPL-3.0 许可证，版权归上游 SensaGram 作者/贡献者所有；重新分发该 APK 前请参阅[许可证说明](./license-notes.zh-CN.md)。

## 数据链路

| APK | 网络链路 | 端侧接收节点 | ROS 输出 |
| --- | --- | --- | --- |
| [`SensaGram-v1.5.2.apk.1.1`](../mobile/android/SensaGram-v1.5.2.apk.1.1) | 默认发送到端侧 UDP `8080` | [`mobile_orientation_receiver_node.py`](../edge/src/NVI/nvi_planning/scripts/mobile_orientation_receiver_node.py) | `/mobile/orientation` |
| [`app-debug-15.apk.1.1.1.1.1`](../mobile/android/app-debug-15.apk.1.1.1.1.1) | 发送到端侧 TCP `1234` | [`nvi_phone_gps.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_phone_gps.launch) | `/phone_gps/receiver_lla`，并 remap 到 `/ublox_driver/receiver_lla` |

[`nvi.launch`](../edge/src/NVI/nvi_bringup/launch/nvi.launch)、[`blind_dreamer.launch`](../edge/src/NVI/nvi_bringup/launch/blind_dreamer.launch) 和 [`nvi_edge.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_edge.launch) 等启动文件默认包含手机 GPS 和方向接收节点。

## 运行要求

| 项目 | 要求 |
| --- | --- |
| 手机 | Android 手机，并授予定位、传感器和网络权限 |
| 网络 | Android 手机和端侧机器处于同一局域网 |
| 端侧防火墙 | 放行 TCP `1234` 用于手机 GPS，放行 UDP `8080` 用于方向数据 |
| 端侧工作空间 | 运行 launch 前需要构建并 source [`edge/`](../edge/) ROS 工作空间 |
| 运行状态 | 保持应用前台运行；Android 可能限制后台定位、传感器或网络访问 |

在应用中配置端侧机器的局域网 IP，不要填写 `127.0.0.1`。在端侧机器查看 IP：

```bash
hostname -I
```

## 安装 APK

可从仓库文件安装，例如：

```bash
adb install mobile/android/SensaGram-v1.5.2.apk.1.1
adb install mobile/android/app-debug-15.apk.1.1.1.1.1
```

也可以把 APK 传到手机后手动安装。Android 可能需要允许安装未知来源应用。

## 验证手机 GPS

启动端侧 GPS 接收节点：

```bash
source /opt/ros/noetic/setup.bash
cd edge
source devel/setup.bash
roslaunch nvi_bringup nvi_phone_gps.launch
```

在 GPS 应用中配置：

```text
Host: <edge-machine-LAN-IP>
Port: 1234
```

保持应用前台运行，并验证 ROS topic：

```bash
rostopic echo /ublox_driver/receiver_lla
```

原始手机 GPS 节点发布 `/phone_gps/receiver_lla`；[`nvi_phone_gps.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_phone_gps.launch) 会将其 remap 到 `/ublox_driver/receiver_lla`，以兼容现有规划栈。

## 验证手机方向

只启动方向接收节点：

```bash
source /opt/ros/noetic/setup.bash
cd edge
source devel/setup.bash
rosrun nvi_planning mobile_orientation_receiver_node.py _udp_port:=8080 _out_topic:=/mobile/orientation
```

如果 SensaGram 应用提供端口配置，请使用端侧机器 IP 和方向端口：

```text
Host: <edge-machine-LAN-IP>
Port: 8080
```

保持应用前台运行，并验证：

```bash
rostopic echo /mobile/orientation
```

接收节点接收类似 JSON 的方向数据，并发布 `nvi_msgs/HeaderFloat32`。如果没有数据，优先检查局域网连通性、防火墙、应用权限、前台运行状态和 IP/端口配置。

## 整机使用

进行手机辅助的室外实验时，先启动 APK 并验证两个 topic，再使用包含移动端接收节点的启动文件：

```bash
roslaunch nvi_bringup blind_dreamer.launch
```

或：

```bash
roslaunch nvi_bringup nvi_edge.launch
```

## 复现边界

- Android 源码不随仓库提供。
- APK 行为可能受 Android 版本和厂商省电策略影响。
- APK 不包含高德凭据。路线规划所需的 `AMAP_API_KEY` 需要在端侧配置。
- 公开部署默认要求应用保持前台运行。
