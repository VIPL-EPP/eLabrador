# 云侧语义服务

[English](./cloud-semantic-server.md) | 简体中文

公开的云侧服务入口为 [`cloud/semantic-server/`](../cloud/semantic-server/)。

本文档描述端侧语义建图默认依赖的可复现路径：通过 HTTP 暴露的 Mask2Former Detectron2 FastAPI 服务。

H100 与 BW1000 的简要性能数据见根目录 README 的
[Mask2Former 云侧推理优化](../README.zh-CN.md#mask2former-云侧推理优化)；依赖补丁、配置和
启动步骤以本文为准。

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

仓库提交了云端优化所需的完整补丁集。将 Mask2Former 固定到已验证 revision 后，按目标
平台执行一次脚本即可按正确顺序应用全部补丁：

```bash
git clone https://github.com/facebookresearch/Mask2Former.git /path/to/Mask2Former
git -C /path/to/Mask2Former checkout 9b0651c6c1d5b3af2e6da0589b719c514ec0d69a

cloud/semantic-server/apply-mask2former-patches.sh h100 /path/to/Mask2Former
# BW1000 使用：
# cloud/semantic-server/apply-mask2former-patches.sh bw1000 /path/to/Mask2Former
```

脚本会先检查源码 revision 和整套补丁的可应用性，任何一步不匹配都不会修改目标源码。
应用后必须重新构建 MultiScaleDeformableAttention extension。补丁清单、平台差异和许可证见
[`cloud/semantic-server/patches/mask2former/`](../cloud/semantic-server/patches/mask2former/)。

## 主要文件

| 路径 | 用途 |
| --- | --- |
| [`cloud/semantic-server/fastapi-mask2former_detectron2.py`](../cloud/semantic-server/fastapi-mask2former_detectron2.py) | 默认 Mask2Former Detectron2 服务 |
| [`cloud/semantic-server/config.py`](../cloud/semantic-server/config.py) | 设备和服务配置 |
| [`cloud/semantic-server/configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml) | 默认 Detectron2 模型配置 |
| [`cloud/semantic-server/apply-mask2former-patches.sh`](../cloud/semantic-server/apply-mask2former-patches.sh) | 一次性应用 H100 或 BW1000 Mask2Former 补丁集 |
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
NVI_FLOAT32_MATMUL_PRECISION=high
NVI_AUTOCAST_DTYPE=none
NVI_SWIN_ATTENTION_IMPL=legacy
NVI_SWIN_FFN_IMPL=legacy
NVI_DECODER_POINTWISE_IMPL=legacy
NVI_MSDEFORM_IMPL=legacy
NVI_MSDEFORM_NORM_IMPL=legacy
NVI_MSDEFORM_FFN_IMPL=legacy
NVI_UPSAMPLE_POINTWISE_IMPL=legacy
NVI_SEMANTIC_BATCH_IMPL=legacy
NVI_NPZ_COMPRESSION_LEVEL=1
NVI_COMPRESS_THREADS=4
NVI_PROFILE_SCHEDULER_TIMING=false
```

补丁脚本只安装实现，不会自动打开实验模式。H100 最终候选配置为：

```bash
NVI_AUTOCAST_DTYPE=bfloat16
NVI_SWIN_ATTENTION_IMPL=flex-bf16-layout-qkv
NVI_SWIN_FFN_IMPL=compiled-bf16
NVI_DECODER_POINTWISE_IMPL=compiled
NVI_MSDEFORM_IMPL=h100-fixed-fp32
NVI_MSDEFORM_NORM_IMPL=compiled
NVI_MSDEFORM_FFN_IMPL=compiled-bf16
NVI_UPSAMPLE_POINTWISE_IMPL=compiled
NVI_SEMANTIC_BATCH_IMPL=compiled-batched
```

BW1000 使用全局 BF16 eager、64-thread MS-Deform，其他依赖内实现保持 `legacy`：

```bash
NVI_AUTOCAST_DTYPE=bfloat16
NVI_SWIN_ATTENTION_IMPL=legacy
NVI_SWIN_FFN_IMPL=legacy
NVI_DECODER_POINTWISE_IMPL=legacy
NVI_MSDEFORM_IMPL=bw1000-fixed-fp32
NVI_MSDEFORM_NORM_IMPL=legacy
NVI_MSDEFORM_FFN_IMPL=legacy
NVI_UPSAMPLE_POINTWISE_IMPL=legacy
NVI_SEMANTIC_BATCH_IMPL=legacy
NVI_USE_CUDA_GRAPH=false
```

固定形状 MS-Deform 仅适用于生产金字塔 `[[24,32],[48,64],[96,128]]`，其他几何必须
使用 `legacy`。H100 选择性 BF16 路径只有 fixture 一致性结果，尚无带标注 mIoU，生产
部署前仍需显式启用并完成任务精度验证。

NPZ 响应默认使用 Deflate level 1，并由独立的 4 线程压缩池编码；编码期间事件循环可继续
接收请求，调度器也可启动下一批 GPU 推理。响应仍是标准 NPZ，`np.load` 调用和字段名无需
修改。可通过 `NVI_NPZ_COMPRESSION_LEVEL` 与 `NVI_COMPRESS_THREADS` 调整或回退。

请求调度默认保持 `NVI_BATCH_POLICY=opportunistic`、`NVI_MAX_BATCH_SIZE=4`、
`NVI_MAX_BATCH_WAIT_MS=0`。请求按源尺寸和输出模式分桶，`return_probs` 不与普通 mask/conf
混批；CUDA Graph key 包含 batch 内每个输入的 tensor shape 和原始输出尺寸。代码另提供
`pipeline`、`adaptive`、`fixed` 策略，以及队列时限、失败冷却等参数，但当前 H100 闭环
压测未发现 1–5 ms 等待的稳定收益，生产默认不启用。

`NVI_PROFILE_SCHEDULER_TIMING=true` 仅用于 Profile：它记录队列、batch 形成、executor、
CUDA 前向、后处理/D2H 和结果回传时间，并增加 NVTX range。正常服务测量应保持关闭；
启用后会增加同步并输出请求级 JSON 日志。

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
