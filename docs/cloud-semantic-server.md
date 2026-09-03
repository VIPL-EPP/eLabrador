# Cloud Semantic Server

English | [简体中文](./cloud-semantic-server.zh-CN.md)

The public cloud service entry point is [`cloud/semantic-server/`](../cloud/semantic-server/).

This document describes the reproducible default path used by the edge semantic mapping stack: a Mask2Former Detectron2 FastAPI service exposed over HTTP.

For concise H100 and BW1000 performance data, see
[Cloud-side Mask2Former Optimization](../README.md#cloud-side-mask2former-optimization).
Use this guide for dependency patches, configuration, and startup.

## Reproduction Target

| Target | Status |
| --- | --- |
| Mask2Former semantic inference over HTTP | Default path for edge integration |
| Mask2Former WebSocket endpoint | Implemented in server and tests, but not used by the default edge detector |

For the edge stack, the endpoint you normally need is:

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

Set that value on the edge machine as `MASK2FORMER_HTTP_URL`.

## Prerequisites

| Item | Requirement |
| --- | --- |
| Server | Linux server with an NVIDIA GPU |
| Container runtime | Docker, Docker Compose, and NVIDIA Container Toolkit |
| Network | Edge machine can reach the cloud server host and `NVI_HOST_PORT` |
| Model files | Mask2Former Detectron2 checkpoint prepared locally |

CUDA, PyTorch, Detectron2, Mask2Former, GPU driver, and checkpoint versions must match the target server. The repository does not include model weights.

## Prepare Mask2Former Dependencies

Prebuilt wheel packages are not distributed in this repository. The base Docker image installs only the generic Python requirements from [`cloud/semantic-server/BaseDocker/requirements.txt`](../cloud/semantic-server/BaseDocker/requirements.txt).

Before building or running the default Mask2Former Detectron2 service, install or build the environment-specific semantic segmentation dependencies for your target server:

- Detectron2
- Mask2Former
- MultiScaleDeformableAttention or other custom operators required by your Mask2Former checkout
- ROS Python bridge packages only if your deployment path needs them inside the cloud container

These packages are sensitive to Python, PyTorch, CUDA, GPU driver, compiler, and Linux architecture versions. Use the upstream project instructions or your lab's reproducible build scripts to install versions that match the target checkpoint and server environment.

The repository includes the complete cloud-optimization patch sets. Pin
Mask2Former to the validated revision, then run the script once for the target
platform; it applies every required patch in order:

```bash
git clone https://github.com/facebookresearch/Mask2Former.git /path/to/Mask2Former
git -C /path/to/Mask2Former checkout 9b0651c6c1d5b3af2e6da0589b719c514ec0d69a

cloud/semantic-server/apply-mask2former-patches.sh h100 /path/to/Mask2Former
# For BW1000, use:
# cloud/semantic-server/apply-mask2former-patches.sh bw1000 /path/to/Mask2Former
```

The script checks the source revision and preflights the complete patch chain;
it leaves the target untouched if any patch does not match. Rebuild the
MultiScaleDeformableAttention extension afterward. See
[`cloud/semantic-server/patches/mask2former/`](../cloud/semantic-server/patches/mask2former/)
for the bundle contents, platform differences, and license.

## Main Files

| Path | Purpose |
| --- | --- |
| [`cloud/semantic-server/fastapi-mask2former_detectron2.py`](../cloud/semantic-server/fastapi-mask2former_detectron2.py) | Default Mask2Former Detectron2 service |
| [`cloud/semantic-server/config.py`](../cloud/semantic-server/config.py) | Device and service configuration |
| [`cloud/semantic-server/configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml) | Default Detectron2 model config |
| [`cloud/semantic-server/apply-mask2former-patches.sh`](../cloud/semantic-server/apply-mask2former-patches.sh) | Apply the complete H100 or BW1000 Mask2Former patch set |
| [`cloud/semantic-server/docker_exec.sh`](../cloud/semantic-server/docker_exec.sh) | Runtime entry script used by Docker Compose |
| [`cloud/semantic-server/.env.example`](../cloud/semantic-server/.env.example) | Environment variable template |

## Prepare Model Files

For the default Detectron2 service, place the checkpoint at:

```text
cloud/semantic-server/models/mask2former-swinL-semantic.pkl
```

This path is referenced by [`configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml).

## Configure `.env`

From [`cloud/semantic-server/`](../cloud/semantic-server/):

```bash
cp .env.example .env
```

Replace every descriptive value in `.env`. A minimal default Mask2Former deployment looks like:

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

The patch script installs implementations but does not enable experimental modes.
The final H100 candidate uses:

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

BW1000 uses global BF16 eager execution and the 64-thread MS-Deform variant; the
other dependency implementations remain on `legacy`:

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

The fixed-shape MS-Deform path supports only the production pyramid
`[[24,32],[48,64],[96,128]]`; use `legacy` for every other geometry. The H100
selective-BF16 path has fixture-consistency results but no labelled-set mIoU, so it
must remain an explicit opt-in until task-accuracy validation is complete.

NPZ responses use Deflate level 1 and are encoded on a dedicated four-thread pool.
The event loop remains available to accept requests while the scheduler starts the
next GPU batch. Responses remain standard NPZ files with unchanged keys, so existing
`np.load` clients require no changes. Tune or roll back with
`NVI_NPZ_COMPRESSION_LEVEL` and `NVI_COMPRESS_THREADS`.

Request scheduling defaults to `NVI_BATCH_POLICY=opportunistic`,
`NVI_MAX_BATCH_SIZE=4`, and `NVI_MAX_BATCH_WAIT_MS=0`. Requests are bucketed by
source size and output mode, so probability responses do not share batches with
normal mask/confidence responses. CUDA Graph keys contain every batched input's
tensor shape and original output size. `pipeline`, `adaptive`, and `fixed` policies,
queue deadlines, and failed-probe cooldown controls remain available for explicit
experiments. An H100 closed-loop benchmark found no stable joint throughput/tail
latency benefit from 1–5 ms waits, so they are not enabled by default.

`NVI_PROFILE_SCHEDULER_TIMING=true` is a profiling-only switch. It records queue,
batch formation, executor, CUDA forward, finalize/D2H, and result-dispatch timing and
adds NVTX ranges. Leave it disabled for normal service measurements; enabling it adds
synchronization and emits per-request JSON records.

## Build And Run

From [`cloud/semantic-server/`](../cloud/semantic-server/):

```bash
mkdir -p models logs
bash build_base_docker.sh v0.1
docker compose up -d
docker compose logs -f server
```

If you build with a specific full-image tag, set `NVI_SERVER_IMAGE` in `.env` to that tag, for example `nvi_server_full:v0.1`.

## Test The HTTP Endpoint

Create a small test image on the cloud machine:

```bash
python3 - <<'PY'
from PIL import Image
Image.new("RGB", (64, 64), (128, 128, 128)).save("/tmp/nvi-cloud-test.jpg")
PY
```

Send it to the service:

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

Inspect the response:

```bash
python3 - <<'PY'
import numpy as np
data = np.load("/tmp/mask2former-result.npz")
print(data.files)
for key in data.files:
    print(key, data[key].shape, data[key].dtype)
PY
```

For edge integration, set the edge-side environment variable:

```bash
export MASK2FORMER_HTTP_URL=http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

## Reproduction Boundary

- Model weights are not included.
- The repository does not provide a verified public URL for `mask2former-swinL-semantic.pkl`; use the checkpoint that matches your experiment and config.
- The included test scripts under [`cloud/semantic-server/tests/`](../cloud/semantic-server/tests/) expect user-provided endpoint variables and test images.
