# Semantic Segmentation Server

English | [简体中文](./README.zh-CN.md)

This directory contains the cloud-side semantic server used by eLabrador.

For full setup, model, Docker, test, and edge-integration instructions, see [Cloud Semantic Server](../../docs/cloud-semantic-server.md).

For concise H100 and BW1000 performance data, see
[Cloud-side Mask2Former Optimization](../../README.md#cloud-side-mask2former-optimization).

## Default Runtime

The reproducible default path is the Mask2Former Detectron2 FastAPI service:

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

Set this URL on the edge machine as `MASK2FORMER_HTTP_URL`.

### Mask2Former optimization patches

The service defaults to FP32 parameters, TF32 matmul, and `legacy` dependency
implementations. The repository includes complete H100 and BW1000 patch sets. From
the repository root, run one command against the pinned Mask2Former checkout:

```bash
cloud/semantic-server/apply-mask2former-patches.sh h100 /path/to/Mask2Former
# Or:
cloud/semantic-server/apply-mask2former-patches.sh bw1000 /path/to/Mask2Former
```

The script validates the revision, work tree, and complete application order. Rebuild
the MultiScaleDeformableAttention extension afterward. See
[`patches/mask2former/`](./patches/mask2former/) for bundle contents and
[Cloud Semantic Server](../../docs/cloud-semantic-server.md) for installation and
runtime switches. Fixed-shape and selective-BF16 modes remain opt-in; do not replace
the `legacy` production defaults until labelled-set mIoU validation is complete.

### Response compression

`/predict` and `/predict_ws` produce standard NPZ responses with Deflate level 1.
Existing clients can continue to use `np.load`; the default keys remain `mask/conf`,
and the HTTP probability path remains `arr_0`. Encoding runs on a dedicated pool
outside the event loop. `NVI_COMPRESS_THREADS` defaults to `4`, and
`NVI_NPZ_COMPRESSION_LEVEL` defaults to `1`.

### Request batching

The service defaults to `NVI_BATCH_POLICY=opportunistic`,
`NVI_MAX_BATCH_SIZE=4`, and `NVI_MAX_BATCH_WAIT_MS=0`. Requests may enter the
queue before resize completes, and the scheduler immediately drains currently
available requests with the same source size and output mode. This preserves
resize/response overlap with GPU waves. Probability responses no longer share a
batch with normal mask/confidence responses, and CUDA Graphs use each input's full
tensor/output-size signature.

`pipeline`, `adaptive`, and `fixed` remain explicit experimental policies. In the
current H100 closed-loop A/B, neither 1–5 ms waits nor a ready-only
pipeline improved throughput and tail latency together, so they are not defaults.

### Scheduler/GPU profiling

Set `NVI_PROFILE_SCHEDULER_TIMING=true` only during profiling. It adds per-request
queue/batch/executor timing, CUDA Events for forward and finalize/D2H, and stable NVTX
ranges. The default is `false`; enabling it introduces synchronization and emits
per-request JSON records.

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
