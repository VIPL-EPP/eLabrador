# nvi_phone_gps

[English](./README.md) | 简体中文

## 功能说明

`nvi_phone_gps` 通过本地 TCP socket 接收 Android 手机端发送的 GPS 定位信息，并将其发布为 ROS topic。

默认监听地址为 `0.0.0.0:1234`。每条消息应包含纬度和经度，格式如下：

```text
40.414306,116.677526
```

节点会向以下 topic 发布 `sensor_msgs/NavSatFix` 消息：

```text
/phone_gps/receiver_lla
```

在 eLabrador 的主 launch 文件中，该 topic 会被 remap 到 `/ublox_driver/receiver_lla`，因此下游模块可以继续使用原来的 GPS topic 名称。
