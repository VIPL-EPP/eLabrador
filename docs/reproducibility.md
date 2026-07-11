# Reproducibility Boundary

English | [简体中文](./reproducibility.zh-CN.md)

This repository is a public research and engineering release for eLabrador. It is not a one-command reproduction package for every physical experiment in the paper.

## Directly Available

- Edge-side ROS source code and launch files
- Cloud semantic server source and Docker deployment assets
- Android APK artifacts for phone GPS and magnetometer/orientation forwarding
- Configuration examples
- Package-level README files

## User-Provided Assets

Users must provide:

- API keys and compatible model-service credentials
- AMap/Gaode Web service key
- Local route files and experiment-site configuration
- Cloud-side Mask2Former checkpoint, optional Qwen-VL weights, and edge-side local model weights
- Datasets, maps, and rosbag files
- RealSense, phone, belt, microphone, and speaker
- External GNSS/RTK hardware and credentials only if you integrate an external positioning driver; see [RTK/GNSS Extensions](./rtk-gnss-extensions.md)

## Suggested Reproduction Levels

| Level | Goal | Requirements |
| --- | --- | --- |
| Code inspection | Understand system modules and paper implementation | Repository only |
| Edge build | Compile ROS packages | Ubuntu 20.04, ROS Noetic, dependencies |
| Sensor test | Run RealSense/phone GPS/belt nodes | Physical devices and local config |
| Cloud test | Start semantic service | GPU server, Mask2Former checkpoint, cloud `.env` |
| Full navigation experiment | Reproduce integrated outdoor navigation workflow | Hardware, route config, credentials, cloud and edge model weights, local environment tuning |

## Notes

Physical navigation behavior depends on hardware mounting, calibration, lighting, phone GPS quality, cloud service availability, phone foreground status, belt connection, local routes, and model versions. If an external GNSS/RTK receiver is integrated, its signal quality and correction service also affect results.
