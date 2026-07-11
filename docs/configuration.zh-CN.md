# 配置

[English](./configuration.md) | 简体中文

运行时凭据和机器相关路径应来自环境变量、本地 `.env` 文件、launch 参数、YAML 文件或本地 JSON 文件。不要提交真实凭据或私有路线文件。

## 环境变量模板

复制根目录模板：

```bash
cp .env.example .env
```

运行前加载：

```bash
set -a
source .env
set +a
```

重要变量包括：

| 变量 | 用途 |
| --- | --- |
| `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL` | OpenAI 兼容多模态/VQA 接口 |
| `DASHSCOPE_API_KEY` | DashScope ASR |
| `AMAP_API_KEY` | 高德/AMap 路线规划 |
| `NVI_LOCAL_PLANNING_MODEL` | 包含 `best_rssm_trajectory_model.pth` 的局部规划模型目录 |
| `BELT_BLUETOOTH_MAC` | HC-05 腰带蓝牙 MAC 地址 |
| `MASK2FORMER_HTTP_URL` | 默认云侧 Mask2Former HTTP 端点 |
| `MASK2FORMER_WS_URI`（可选） | 非默认 WebSocket detector 端点 |

## 本地资产路径

推荐本地目录：

| 路径 | 用途 | 是否提交 |
| --- | --- | --- |
| `data/` | 数据集、地图、测试图片、rosbag 文件 | 否 |
| `data/rosbags/` | rosbag 输入或采集文件 | 否 |
| `models/` | 端侧局部规划、OCR、交通灯等本地模型权重 | 否 |
| `output/`、`outputs/` | 生成结果 | 否 |
| `logs/` | 运行日志 | 否 |

RSSM 局部规划 checkpoint 可从 [Google Drive](https://drive.google.com/file/d/1mid3cVu4RZW96qWVOgOr6-XL6GBNSkLD/view) 下载。请将其放在 `models/best_rssm_trajectory_model.pth`，或将 `NVI_LOCAL_PLANNING_MODEL` 设置为包含 `best_rssm_trajectory_model.pth` 的其他目录。

## 管理模块配置

公开的路线和关键消息示例位于 [`edge/src/NVI/nvi_management/config/`](../edge/src/NVI/nvi_management/config/)。

```bash
cp edge/src/NVI/nvi_management/config/key_msg.example.json edge/src/NVI/nvi_management/config/key_msg.json
cp edge/src/NVI/nvi_management/config/route_config.example.json edge/src/NVI/nvi_management/config/route_config.json
```

请按本地实验场地修改这些本地副本。不要提交真实路线、家庭、单位、实验室或账号信息。

## 设备别名

udev 规则位于 [`edge/src/NVI/system_config/99-nvi-usb.rules`](../edge/src/NVI/system_config/99-nvi-usb.rules)。

根目录 `.env.example` 包含默认腰带别名 `/dev/ttyBelt`。外部 GNSS/RTK 驱动应在默认配置之外自行定义串口别名；见 [RTK/GNSS 扩展](./rtk-gnss-extensions.zh-CN.md)。
