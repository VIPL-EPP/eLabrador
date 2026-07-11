# 语义分割服务器端

[English](./README.md) | 简体中文

该目录包含 eLabrador 使用的云侧语义服务。

完整的安装、模型、Docker、测试和端侧集成说明见 [云侧语义服务](../../docs/cloud-semantic-server.zh-CN.md)。

## 默认运行路径

可复现的默认路径是 Mask2Former Detectron2 FastAPI 服务：

```text
http://<cloud-host>:<NVI_HOST_PORT>/mask2former/predict
```

在端侧机器上将该 URL 配置为 `MASK2FORMER_HTTP_URL`。

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
