# Cloud Semantic Server

English | [简体中文](./cloud-semantic-server.zh-CN.md)

The public cloud service entry point is [`cloud/semantic-server/`](../cloud/semantic-server/).

This document describes the reproducible default path used by the edge semantic mapping stack: a Mask2Former Detectron2 FastAPI service exposed over HTTP.

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

## Main Files

| Path | Purpose |
| --- | --- |
| [`cloud/semantic-server/fastapi-mask2former_detectron2.py`](../cloud/semantic-server/fastapi-mask2former_detectron2.py) | Default Mask2Former Detectron2 service |
| [`cloud/semantic-server/config.py`](../cloud/semantic-server/config.py) | Device and service configuration |
| [`cloud/semantic-server/configs/mask2former_detectron2_model.yaml`](../cloud/semantic-server/configs/mask2former_detectron2_model.yaml) | Default Detectron2 model config |
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
```

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
