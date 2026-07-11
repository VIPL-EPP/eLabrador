# nvi_phone_gps

English | [简体中文](./README.zh-CN.md)

## Overview

`nvi_phone_gps` receives GPS positions from the Android mobile app over a local TCP socket and publishes them as a ROS topic.

By default, the node listens on `0.0.0.0:1234`. Each message should contain latitude and longitude in the following format:

```text
40.414306,116.677526
```

The node publishes `sensor_msgs/NavSatFix` messages to:

```text
/phone_gps/receiver_lla
```

In the main eLabrador launch files, this topic is remapped to `/ublox_driver/receiver_lla` so existing downstream modules can keep using the original GPS topic name.
