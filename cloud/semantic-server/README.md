# Semantic Segmentation Server

English | [简体中文](./README.zh-CN.md)

This directory contains the cloud-side semantic server used by eLabrador.

For full setup, model, Docker, test, and edge-integration instructions, see [Cloud Semantic Server](../../docs/cloud-semantic-server.md).

## Default Runtime

The reproducible default path is the Mask2Former Detectron2 FastAPI service:

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

Set this URL on the edge machine as `MASK2FORMER_HTTP_URL`.

## Minimal Checklist

1. Prepare a Linux GPU server with Docker, Docker Compose, and NVIDIA Container Toolkit.
2. Place the default Mask2Former checkpoint provided by the default Mask2Former repo trained on the MapillaryVistas dataset at:

```text
models/mask2former-swinL-semantic.pkl
```

3. Copy `.env.example` to `.env` and replace every descriptive placeholder.
4. Build and start:

```bash
bash build_base_docker.sh v0.1
docker compose up -d
```

Prebuilt wheel packages are not included. Install or build Detectron2, Mask2Former, and required custom operators for the target Python, PyTorch, CUDA, and server environment before using the default service image.

5. Check logs:

```bash
docker compose logs -f server
```
