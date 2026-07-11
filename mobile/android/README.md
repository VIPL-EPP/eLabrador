# Android Apps

English | [简体中文](./README.zh-CN.md)

This directory provides Android APK artifacts for feeding phone-side data into the eLabrador edge ROS system.

For full setup and verification instructions, see [Mobile Android Apps](../../docs/mobile-android.md).

## APKs

| File | Network path | Edge output |
| --- | --- | --- |
| `SensaGram-v1.5.2.apk.1.1` | UDP to edge port `8080` by default | `/mobile/orientation` |
| `app-debug-15.apk.1.1.1.1.1` | TCP to edge port `1234` | `/ublox_driver/receiver_lla` through `nvi_phone_gps.launch` |

## Minimal Checks

1. Install the required APKs on an Android phone.
2. Put the phone and edge machine on the same LAN.
3. Configure the edge machine LAN IP in the app.
4. Keep the app in the foreground.
5. Verify on the edge machine:

```bash
rostopic echo /ublox_driver/receiver_lla
rostopic echo /mobile/orientation
```

Android source code is not included in this repository.
