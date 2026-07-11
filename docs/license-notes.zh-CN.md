# 许可证说明

[English](./license-notes.md) | 简体中文

除文件或目录另有说明外，本项目自有代码按 GPLv3 发布。第三方代码、模型权重、数据集、配置文件和二进制文件仍受其原始许可证和条款约束。

## 源码树中的主要第三方组件

| 组件 | 路径 | 本地许可证说明 |
| --- | --- | --- |
| Semantic SLAM | [`edge/src/NVI/semantic_slam`](../edge/src/NVI/semantic_slam) | GPLv3 |
| VINS-Mono | [`edge/src/NVI/nvi_vio/VINS-Mono`](../edge/src/NVI/nvi_vio/VINS-Mono) | GPLv3，子组件有各自条款 |
| DBoW2 | [`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DBoW`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DBoW) | CC BY-NC-SA 3.0 |
| DUtils / DVision | [`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DUtils`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DUtils)、[`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DVision`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DVision) | LGPLv3 or later |
| ASRT Speech Recognition Tool | [`edge/src/NVI/nvi_speech/src/asrt_sdk_ros`](../edge/src/NVI/nvi_speech/src/asrt_sdk_ros) | GPLv3 or later |
| SensaGram Android APK | [`mobile/android/SensaGram-v1.5.2.apk.1.1`](../mobile/android/SensaGram-v1.5.2.apk.1.1) | 来自第三方项目 [`UmerCodez/SensaGram`](https://github.com/UmerCodez/SensaGram) 的 `v1.5.2` 发布版二进制文件；许可证为 GPL-3.0；版权归上游 SensaGram 作者/贡献者所有 |

## 外部服务

用户配置后，全局路线规划会调用高德/AMap API。用户需要遵守服务提供方 API 条款，并自行提供 `AMAP_API_KEY`。

## 外部 RTK/GNSS 参考

RTK/GNSS 驱动不再随默认源码树内置。如果自行集成外部定位项目，请分别核查其许可证。见 [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md)。

发布二进制包、模型产物、数据集或 Docker 镜像前，应分别核查所有打包依赖和模型/数据资产的许可证。
