# Configuration

English | [简体中文](./configuration.zh-CN.md)

Runtime credentials and machine-specific paths should come from environment variables, local `.env` files, launch arguments, YAML files, or local JSON files. Do not commit real credentials or private route files.

## Environment Template

Copy the root template:

```bash
cp .env.example .env
```

Load it before running:

```bash
set -a
source .env
set +a
```

Important variables include:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | OpenAI-compatible multimodal/VQA endpoint |
| `DASHSCOPE_API_KEY` | DashScope ASR |
| `AMAP_API_KEY` | AMap/Gaode route planning |
| `NVI_LOCAL_PLANNING_MODEL` | Local planning model directory containing `best_rssm_trajectory_model.pth` |
| `BELT_BLUETOOTH_MAC` | HC-05 belt Bluetooth MAC address |
| `MASK2FORMER_HTTP_URL` | Default cloud Mask2Former HTTP endpoint |
| `MASK2FORMER_WS_URI` (optional) | Non-default WebSocket detector endpoint |

## Local Asset Paths

Recommended local directories:

| Path | Purpose | Commit? |
| --- | --- | --- |
| `data/` | datasets, maps, test images, rosbag files | no |
| `data/rosbags/` | rosbag input or captured files | no |
| `models/` | Edge-side local-planning, OCR, traffic-light, and other local model weights | no |
| `output/`, `outputs/` | generated outputs | no |
| `logs/` | runtime logs | no |

The RSSM local-planning checkpoint can be downloaded from [Google Drive](https://drive.google.com/file/d/1mid3cVu4RZW96qWVOgOr6-XL6GBNSkLD/view). Place it at `models/best_rssm_trajectory_model.pth`, or set `NVI_LOCAL_PLANNING_MODEL` to another directory that contains `best_rssm_trajectory_model.pth`.

## Management Config

Public route and key-message examples live in [`edge/src/NVI/nvi_management/config/`](../edge/src/NVI/nvi_management/config/).

```bash
cp edge/src/NVI/nvi_management/config/key_msg.example.json edge/src/NVI/nvi_management/config/key_msg.json
cp edge/src/NVI/nvi_management/config/route_config.example.json edge/src/NVI/nvi_management/config/route_config.json
```

Edit those local copies for your experiment site. Do not commit real route, home, office, lab, or account information.

## Device Aliases

udev rules are under [`edge/src/NVI/system_config/99-nvi-usb.rules`](../edge/src/NVI/system_config/99-nvi-usb.rules).

The root `.env.example` includes the default belt alias `/dev/ttyBelt`. External GNSS/RTK drivers should define their own serial aliases outside the default configuration; see [RTK/GNSS Extensions](./rtk-gnss-extensions.md).
