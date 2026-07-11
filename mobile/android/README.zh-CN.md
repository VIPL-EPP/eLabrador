# Android 应用说明

[English](./README.md) | 简体中文

该目录提供 Android APK 产物，用于把手机侧数据接入 eLabrador 端侧 ROS 系统。

完整安装和验证流程见 [Android 移动端应用](../../docs/mobile-android.zh-CN.md)。

## APK

| 文件 | 网络链路 | 端侧输出 |
| --- | --- | --- |
| `SensaGram-v1.5.2.apk.1.1` | 默认发送到端侧 UDP `8080` | `/mobile/orientation` |
| `app-debug-15.apk.1.1.1.1.1` | 发送到端侧 TCP `1234` | 通过 `nvi_phone_gps.launch` 输出到 `/ublox_driver/receiver_lla` |

## 最小检查

1. 在 Android 手机上安装所需 APK。
2. 将手机和端侧机器接入同一局域网。
3. 在应用中配置端侧机器局域网 IP。
4. 保持应用前台运行。
5. 在端侧机器验证：

```bash
rostopic echo /ublox_driver/receiver_lla
rostopic echo /mobile/orientation
```

本仓库不包含 Android 源码。
