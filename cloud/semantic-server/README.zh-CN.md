# 语义分割服务器端

[English](./README.md) | 简体中文

该目录包含 eLabrador 使用的云侧语义服务。

完整的安装、模型、Docker、测试和端侧集成说明见 [云侧语义服务](../../docs/cloud-semantic-server.zh-CN.md)。

H100 与 BW1000 的简要性能数据见根目录 README 的
[Mask2Former 云侧推理优化](../../README.zh-CN.md#mask2former-云侧推理优化)。

## 默认运行路径

可复现的默认路径是 Mask2Former Detectron2 FastAPI 服务：

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

在端侧机器上将该 URL 配置为 `MASK2FORMER_HTTP_URL`。

### Mask2Former 优化补丁

服务默认使用 FP32 参数、TF32 matmul，并让依赖内优化保持 `legacy`。仓库提交了 H100 和
BW1000 的完整补丁集；在仓库根目录对固定 revision 的 Mask2Former 执行一次：

```bash
cloud/semantic-server/apply-mask2former-patches.sh h100 /path/to/Mask2Former
# 或：
cloud/semantic-server/apply-mask2former-patches.sh bw1000 /path/to/Mask2Former
```

脚本会检查 revision、工作区和整套应用顺序，随后需要重新构建
MultiScaleDeformableAttention extension。补丁内容与平台差异见
[`patches/mask2former/`](./patches/mask2former/)，安装和优化开关见
[云侧语义服务文档](../../docs/cloud-semantic-server.zh-CN.md)。固定形状和选择性 BF16 模式
仍为 opt-in；完成带标注 mIoU 验证前不要替换 `legacy` 生产默认值。

### 响应压缩

`/predict` 与 `/predict_ws` 使用 Deflate level 1 生成标准 NPZ；现有客户端仍可直接
通过 `np.load` 读取，默认响应键保持 `mask/conf`，HTTP 概率路径保持 `arr_0`。编码在
独立线程池中执行，可通过 `NVI_COMPRESS_THREADS`（默认 `4`）设置线程数；
`NVI_NPZ_COMPRESSION_LEVEL` 默认为 `1`。

### 请求组批

服务默认使用 `NVI_BATCH_POLICY=opportunistic`、`NVI_MAX_BATCH_SIZE=4`、
`NVI_MAX_BATCH_WAIT_MS=0`：请求在 resize 尚未完成时即可早入队，调度器立即收走当前已有的
同尺寸、同输出模式请求。这使 resize/响应处理与 GPU 波次重叠；`return_probs` 不再与普通
mask/conf 请求混批，CUDA Graph 也按每个输入的 tensor shape 与输出尺寸完整索引。

`pipeline`、`adaptive`、`fixed` 策略保留为显式实验项。在当前 H100 闭环 A/B 中，
1–5 ms 等待及 ready-only pipeline 均未同时改善吞吐和尾延迟，因此不设为默认。

### 调度/GPU Profile

仅在 Profile 时设置 `NVI_PROFILE_SCHEDULER_TIMING=true`。该开关增加请求级队列、组批和
executor 计时，为前向及后处理/D2H 增加 CUDA Event，并写入稳定 NVTX range。默认值为
`false`；开启后会引入同步并输出请求级 JSON 日志。

## 最小检查清单

1. 准备带 GPU 的 Linux 服务器，并安装 Docker、Docker Compose 和 NVIDIA Container Toolkit。
2. 将默认 Mask2Former 仓库提供的 MapillaryVistas 数据集训练的 checkpoint 放在：

```text
models/mask2former-swinL-semantic.pkl
```

3. 复制 `.env.example` 为 `.env`，并替换所有说明性占位值。
4. 构建并启动：

```bash
bash build_base_docker.sh v0.1
docker compose up -d
```

仓库不包含预构建 wheel 包。使用默认服务镜像前，请根据目标 Python、PyTorch、CUDA 和服务器环境自行安装或构建 Detectron2、Mask2Former 及所需自定义算子。

5. 查看日志：

```bash
docker compose logs -f server
```
