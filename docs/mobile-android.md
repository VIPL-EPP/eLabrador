# Mobile Android Apps

English | [简体中文](./mobile-android.zh-CN.md)

Android helper APKs are stored under [`mobile/android/`](../mobile/android/). They forward phone-side sensor data to the edge ROS system.

This repository provides APK artifacts only, not the Android source projects. Reproduction for this module means installing the APKs, connecting them to the edge machine, and verifying that ROS topics receive data.

`SensaGram-v1.5.2.apk.1.1` is a third-party SensaGram `v1.5.2` APK from [`UmerCodez/SensaGram`](https://github.com/UmerCodez/SensaGram). It is licensed under GPL-3.0, and copyright remains with the upstream SensaGram authors/contributors. See [License Notes](./license-notes.md) before redistributing the APK.

## Data Paths

| APK | Network path | Edge receiver | ROS output |
| --- | --- | --- | --- |
| [`SensaGram-v1.5.2.apk.1.1`](../mobile/android/SensaGram-v1.5.2.apk.1.1) | UDP to edge port `8080` by default | [`mobile_orientation_receiver_node.py`](../edge/src/NVI/nvi_planning/scripts/mobile_orientation_receiver_node.py) | `/mobile/orientation` |
| [`app-debug-15.apk.1.1.1.1.1`](../mobile/android/app-debug-15.apk.1.1.1.1.1) | TCP to edge port `1234` | [`nvi_phone_gps.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_phone_gps.launch) | `/phone_gps/receiver_lla`, remapped to `/ublox_driver/receiver_lla` |

Launch files such as [`nvi.launch`](../edge/src/NVI/nvi_bringup/launch/nvi.launch), [`blind_dreamer.launch`](../edge/src/NVI/nvi_bringup/launch/blind_dreamer.launch), and [`nvi_edge.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_edge.launch) include the phone GPS and orientation receivers by default.

## Requirements

| Item | Requirement |
| --- | --- |
| Phone | Android phone with location, sensor, and network permissions granted |
| Network | Android phone and edge machine on the same LAN |
| Edge firewall | Allow inbound TCP `1234` for phone GPS and UDP `8080` for orientation |
| Edge workspace | Build and source the [`edge/`](../edge/) ROS workspace before running launch files |
| Runtime behavior | Keep the apps in the foreground; Android may restrict background location, sensor, or network access |

Use the edge machine LAN IP, not `127.0.0.1`, when configuring the apps. On the edge machine:

```bash
hostname -I
```

## Install APKs

Install from the repository files, for example:

```bash
adb install mobile/android/SensaGram-v1.5.2.apk.1.1
adb install mobile/android/app-debug-15.apk.1.1.1.1.1
```

You can also transfer the APKs to the phone and install them manually. Android may require enabling installation from unknown sources.

## Verify Phone GPS

Start the edge-side GPS receiver:

```bash
source /opt/ros/noetic/setup.bash
cd edge
source devel/setup.bash
roslaunch nvi_bringup nvi_phone_gps.launch
```

Configure the GPS app with:

```text
Host: <edge-machine-LAN-IP>
Port: 1234
```

Keep the app in the foreground and verify the ROS topic:

```bash
rostopic echo /ublox_driver/receiver_lla
```

The raw phone GPS node publishes `/phone_gps/receiver_lla`; [`nvi_phone_gps.launch`](../edge/src/NVI/nvi_bringup/launch/nvi_phone_gps.launch) remaps it to `/ublox_driver/receiver_lla` for compatibility with the existing planning stack.

## Verify Phone Orientation

Start only the orientation receiver:

```bash
source /opt/ros/noetic/setup.bash
cd edge
source devel/setup.bash
rosrun nvi_planning mobile_orientation_receiver_node.py _udp_port:=8080 _out_topic:=/mobile/orientation
```

Configure SensaGram with the edge machine IP and the orientation port if the app exposes a port field:

```text
Host: <edge-machine-LAN-IP>
Port: 8080
```

Keep the app in the foreground and verify:

```bash
rostopic echo /mobile/orientation
```

The receiver accepts JSON-like orientation payloads and publishes `nvi_msgs/HeaderFloat32` values. If no data arrives, check LAN connectivity, firewall rules, app permissions, foreground status, and the configured IP/port.

## Full-Stack Use

For mobile-assisted outdoor experiments, start the APKs first, verify both topics, then use a launch file that includes the mobile receivers:

```bash
roslaunch nvi_bringup blind_dreamer.launch
```

or:

```bash
roslaunch nvi_bringup nvi_edge.launch
```

## Reproduction Boundary

- Android source code is not included.
- APK behavior may vary across Android versions and vendor battery policies.
- The APKs do not include AMap credentials. Configure `AMAP_API_KEY` on the edge side for route planning.
- Public deployment assumes foreground app operation.
