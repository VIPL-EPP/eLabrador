# RTK/GNSS Extensions

English | [简体中文](./rtk-gnss-extensions.zh-CN.md)

The public edge workspace defaults to Android phone GPS through [`edge/src/NVI/nvi_phone_gps/`](../edge/src/NVI/nvi_phone_gps/). Bundled u-blox, QFRTK, GNSS raw-measurement, and NTRIP client packages are not included in the default source tree.

To use an external GNSS/RTK receiver, add the driver in your own workspace and publish `sensor_msgs/NavSatFix` to `/ublox_driver/receiver_lla`, or update the planning launch/configuration to subscribe to another topic.

## Reference Projects

| Purpose | Reference |
| --- | --- |
| u-blox ZED-F9P ROS driver | [HKUST-Aerial-Robotics/ublox_driver](https://github.com/HKUST-Aerial-Robotics/ublox_driver) |
| GNSS raw-measurement utilities and messages | [HKUST-Aerial-Robotics/gnss_comm](https://github.com/HKUST-Aerial-Robotics/gnss_comm) |
| RTKLIB and `str2str` NTRIP tooling | [tomojitakasu/RTKLIB](https://github.com/tomojitakasu/RTKLIB) |
| ROS NTRIP client | [LORD-MicroStrain/ntrip_client](https://github.com/LORD-MicroStrain/ntrip_client) |

QFRTK T3 support is not bundled. If you use a QFRTK receiver, integrate the vendor or lab-maintained driver outside this repository and bridge its `NavSatFix` output into the same positioning topic expected by the planning stack.
