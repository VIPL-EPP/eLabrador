# 云侧语义服务

[English](./cloud-semantic-server.md) | 简体中文

公开的云侧服务入口为 [`cloud/semantic-server/`](../cloud/semantic-server/)。

本文档描述端侧语义建图默认依赖的可复现路径：通过 HTTP 暴露的 Mask2Former Detectron2 FastAPI 服务。

## 复现目标

| 目标 | 状态 |
| --- | --- |
| 通过 HTTP 提供 Mask2Former 语义推理 | 端侧集成的默认路径 |
| Mask2Former WebSocket 端点 | 服务端和测试脚本中存在，但默认端侧 detector 不使用 |

端侧通常需要配置的端点是：

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

将该地址在端侧配置为 `MASK2FORMER_HTTP_URL`。

## 前置条件

| 项目 | 要求 |
| --- | --- |
| 服务器 | 带 NVIDIA GPU 的 Linux 服务器 |
| 容器运行时 | Docker、Docker Compose 和 NVIDIA Container Toolkit |
| 网络 | 端侧机器能访问云侧服务器主机和 `NVI_HOST_PORT` |
| 模型文件 | 本地准备 Mask2Former Detectron2 checkpoint |

CUDA、PyTorch、Detectron2、Mask2Former、GPU 驱动和 checkpoint 版本必须与目标服务器匹配。仓库不包含模型权重。

## 准备 Mask2Former 依赖

本仓库不再分发预构建 wheel 包。基础 Docker 镜像只安装 [`cloud/semantic-server/BaseDocker/requirements.txt`](../cloud/semantic-server/BaseDocker/requirements.txt) 中的通用 Python 依赖。

构建或运行默认 Mask2Former Detectron2 服务前，请根据目标服务器环境自行安装或构建语义分割相关依赖：

- Detectron2
- Mask2Former
- MultiScaleDeformableAttention 或当前 Mask2Former 代码所需的其他自定义算子
- 仅当云侧容器部署路径需要时，才安装 ROS Python bridge 相关包

这些依赖对 Python、PyTorch、CUDA、GPU 驱动、编译器和 Linux 架构版本敏感。请参考上游项目说明或实验室内部可复现构建脚本，安装与 checkpoint 和目标服务器匹配的版本。

## 主要文件

| 路径 | 用途 |
| --- | --- |
| [`cloud/semantic-server/fastapi-mask2former_detectron2.py`](../cloud/semantic-server/fastapi-mask2former_detectron2.py) | 默认 Mask2Former Detectron2 服务 |
| [`cloud/semantic-server/config.py`](../cloud/semantic-server/config.py) | 设备和服务配置 |
| [`cloud/semantic-server/configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml) | 默认 Detectron2 模型配置 |
| [`cloud/semantic-server/docker_exec.sh`](../cloud/semantic-server/docker_exec.sh) | Docker Compose 使用的运行入口 |
| [`cloud/semantic-server/.env.example`](../cloud/semantic-server/.env.example) | 环境变量模板 |

## 准备模型文件

默认 Detectron2 服务需要将 checkpoint 放在：

```text
cloud/semantic-server/models/mask2former-swinL-semantic.pkl
```

该路径由 [`configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml) 引用。

## 配置 `.env`

在 [`cloud/semantic-server/`](../cloud/semantic-server/) 下执行：

```bash
cp .env.example .env
```

替换 `.env` 中每一个说明性占位值。一个最小默认 Mask2Former 部署示例如下：

```bash
NVI_CONTAINER_USER=root
NVI_HOST_PORT=8001
NVI_GPU_DEVICE_ID=0
NVI_CONTAINER_NAME=nvi-semantic-server
```

## 构建与运行

在 [`cloud/semantic-server/`](../cloud/semantic-server/) 下执行：

```bash
mkdir -p models logs
bash build_base_docker.sh v0.1
docker compose up -d
docker compose logs -f server
```

## 测试 HTTP 端点

在云侧机器创建一张测试图片：

```bash
python3 - <<'PY'
from PIL import Image
Image.new("RGB", (64, 64), (128, 128, 128)).save("/tmp/nvi-cloud-test.jpg")
PY
```

发送到服务：

```bash
set -a
source .env
set +a
curl -f \
  -F image=@/tmp/nvi-cloud-test.jpg \
  -F return_probs=false \
  -o /tmp/mask2former-result.npz \
  http://127.0.0.1:${NVI_HOST_PORT}/mask2former/predict
```

检查返回内容：

```bash
python3 - <<'PY'
import numpy as np
data = np.load("/tmp/mask2former-result.npz")
print(data.files)
for key in data.files:
    print(key, data[key].shape, data[key].dtype)
PY
```

端侧集成时，在端侧机器设置：

```bash
export MASK2FORMER_HTTP_URL=http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

## 复现边界

- 模型权重不随仓库分发。
- 仓库没有提供 `mask2former-swinL-semantic.pkl` 的已验证公开下载地址；请使用与实验和配置匹配的 checkpoint。
- [`cloud/semantic-server/tests/`](../cloud/semantic-server/tests/) 下的测试脚本需要用户自行提供端点变量和测试图片。
