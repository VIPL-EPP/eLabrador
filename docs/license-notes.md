# License Notes

English | [简体中文](./license-notes.zh-CN.md)

Unless a file or directory states otherwise, project-owned code is released under GPLv3. Third-party code, model weights, datasets, configuration files, and binary artifacts remain under their original licenses and terms.

## Third-Party Components Present in the Source Tree

| Component | Path | Local license note |
| --- | --- | --- |
| Semantic SLAM | [`edge/src/NVI/semantic_slam`](../edge/src/NVI/semantic_slam) | GPLv3 |
| VINS-Mono | [`edge/src/NVI/nvi_vio/VINS-Mono`](../edge/src/NVI/nvi_vio/VINS-Mono) | GPLv3, with subcomponents under their own terms |
| DBoW2 | [`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DBoW`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DBoW) | CC BY-NC-SA 3.0 |
| DUtils / DVision | [`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DUtils`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DUtils), [`edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DVision`](../edge/src/NVI/nvi_vio/VINS-Mono/pose_graph/src/ThirdParty/DVision) | LGPLv3 or later |
| ASRT Speech Recognition Tool | [`edge/src/NVI/nvi_speech/src/asrt_sdk_ros`](../edge/src/NVI/nvi_speech/src/asrt_sdk_ros) | GPLv3 or later |
| SensaGram Android APK | [`mobile/android/SensaGram-v1.5.2.apk.1.1`](../mobile/android/SensaGram-v1.5.2.apk.1.1) | Third-party binary from [`UmerCodez/SensaGram`](https://github.com/UmerCodez/SensaGram), release `v1.5.2`; GPL-3.0; copyright remains with the upstream SensaGram authors/contributors |
| Mask2Former optimization patches | [`cloud/semantic-server/patches/mask2former`](../cloud/semantic-server/patches/mask2former) | Modifications to Meta's Mask2Former sources; the upstream MIT license and copyright notice are retained with the patches |

## External Services

Global route planning uses AMap/Gaode APIs when configured by the user. Users must follow the provider's API terms and supply their own `AMAP_API_KEY`.

## External RTK/GNSS References

RTK/GNSS drivers are no longer bundled in the default source tree. If you integrate external positioning projects, review their licenses separately. See [RTK/GNSS Extensions](./rtk-gnss-extensions.md).

Before publishing binaries, model artifacts, datasets, or Docker images, check the licenses of all bundled dependencies and model/data assets.
