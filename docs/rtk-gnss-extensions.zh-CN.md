# RTK/GNSS 扩展

[English](./rtk-gnss-extensions.md) | 简体中文

公开的端侧工作空间默认通过 [`edge/src/NVI/nvi_phone_gps/`](../edge/src/NVI/nvi_phone_gps/) 使用 Android 手机 GPS。默认源码树不再内置 u-blox、QFRTK、GNSS 原始观测或 NTRIP client package。

如果需要接入外部 GNSS/RTK 接收机，请在自己的工作空间加入对应驱动，并将 `sensor_msgs/NavSatFix` 发布到 `/ublox_driver/receiver_lla`；也可以修改规划相关 launch/configuration，让规划栈订阅其他定位 topic。

## 参考项目

| 用途 | 参考 |
| --- | --- |
| u-blox ZED-F9P ROS driver | [HKUST-Aerial-Robotics/ublox_driver](https://github.com/HKUST-Aerial-Robotics/ublox_driver) |
| GNSS 原始观测工具和消息定义 | [HKUST-Aerial-Robotics/gnss_comm](https://github.com/HKUST-Aerial-Robotics/gnss_comm) |
| RTKLIB 和 `str2str` NTRIP 工具 | [tomojitakasu/RTKLIB](https://github.com/tomojitakasu/RTKLIB) |
| ROS NTRIP client | [LORD-MicroStrain/ntrip_client](https://github.com/LORD-MicroStrain/ntrip_client) |

QFRTK T3 支持不随默认仓库内置。如果使用 QFRTK 接收机，请在本仓库之外接入厂商或实验室维护的驱动，并把它输出的 `NavSatFix` 桥接到规划栈期望的定位 topic。
