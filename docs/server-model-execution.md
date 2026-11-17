# 服务器模型部署执行记录

更新：2026-10-11 10:32（北京时间）。**两款模型已下载完成并在服务器真实返回答案；专用模型服务已恢复，当前使用 CPU。** 这是部署和接口可用性记录，平台内的实验记录另见 `verification.md`。

## 实际位置与访问

- SSH 配置别名：`gpu-server`；登录用户 `jmy`，主机 `qilin`，地址 `10.50.2.29`。
- 平台目录：`/home/jmy/reading-bench`。
- 模型权重：`/home/jmy/reading-bench/runtime/models`，共约 9.60 GB（包含两个模型的 config/layer 文件）。
- 模型服务：`127.0.0.1:11435`，本项目独立 tmux 会话 `reading-bench-ollama`。
- Ollama：复用服务器已有 `/usr/local/bin/ollama`，实际版本 `0.13.5`。
- 当前运行配置：`CUDA_VISIBLE_DEVICES=-1`、单个已加载模型、单并发。平台逐题串行调用该服务。

权重来自 Ollama 官方 registry，不会存到本机桌面、服务器公共模型目录或其他用户的项目中。下载日志保留于 `runtime/logs/qwen-pull.log` 与 `runtime/logs/llama-pull.log`。此次恢复直接复用完整权重，没有重复下载。

连接使用本机校园 WLAN 的逐连接中继。WLAN 地址变化时只更新本任务连接参数，没有改动全局路由、代理或其他 SSH 配置。平台通过 SSH 隧道访问，模型端口只监听服务器回环地址。

## 权重身份核验

2026-10-10 21:52（北京时间）两个下载均已完成。服务器上的每份 manifest、全部 config/layer 文件已逐个核对 SHA256 和声明大小，两个模型各 5 个 blob 均通过。2026-10-11 恢复后 `/api/tags` 仍报告相同固定摘要。

| 模型 | 冻结的 manifest SHA256 | 文件总大小 | 量化 |
|---|---|---:|---|
| `qwen2.5:7b-instruct` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | 4,683,087,332 字节 | Q4_K_M |
| `llama3.1:8b-instruct-q4_K_M` | `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` | 4,920,753,328 字节 | Q4_K_M |

完整文件验证原始记录：`output/server-evidence/server-cpu-complete-evidence.json`。`server-model-manifest.json` 是早期采集记录，保留其当时的未验证来源标签；后续文件哈希验证和固定官方来源说明以本记录及原始证据为准，不改写历史记录。

原模型说明快照固定到版本：

- Qwen：`Qwen/Qwen2.5-7B-Instruct`，revision `a09a35458c702b33eeacc393d103063234e8bc28`。
- Llama：`meta-llama/llama-models` 官方模型卡，commit `e2e67cd8b0feca839666b7082dcc1c4fc0ae11e2`。Hugging Face README 需鉴权，实际使用官方 GitHub 固定提交的说明文件。

来源 URL、抓取时间、文件 SHA256 和卡片保存在 `docs/model-source-snapshots/`。这些证据验证 Ollama 分发文件身份，但不构成 GGUF 与原始 tensor 的密码学转换认证，也没有证明完整训练履历。模型发布早于题库文章可以降低污染风险，不能据此宣称零污染。

## 两次资源复查与当前 CPU 选择

2026-10-10 的较早快照只枚举到 3 张 RTX 3090（0、1、2），每张空闲 24,124 MiB、无 compute process。但当时 CUDA 驱动初始化 `cuInit` 返回 `999 / CUDA_ERROR_UNKNOWN`，PyTorch 的独立初始化也失败。因此当日没有成功启用 GPU，改用 CPU 完成真实模型调用。原失败证据 `gpu-readiness.json` 和 `gpu-pytorch-check.json` 已保留。

2026-10-11 10:32（北京时间）重新登录同一主机后，当前实际状态变为：

- 4 张 RTX 3090，每张总显存 24,576 MiB；驱动 `580.105.08`。
- 四张卡各有现存 `VLLM::EngineCore` compute process，占用 9,688 MiB；空闲显存约 14,427–14,428 MiB。
- 新的只读 CUDA 初始化检查 `cuInit=0`、`cuDeviceGetCount=0`，说明驱动初始化此次已恢复。

本项目的 GPU 启动条件是目标卡至少空闲 18 GiB 且没有 compute process。当前四卡均未满足条件，所以恢复专用 CPU 服务。没有停止其他进程、重置 GPU、安装驱动或改变已有 vLLM 服务。今后资源可用时可按 `deploy/start-isolated-ollama.sh` 的检查切换；不能仅凭旧指南或旧快照判断可用性。

新证据保存在 `output/server-evidence/gpu-readiness-20261011.json` 与 `server-service-resume-20261011.json`，没有覆盖 10 月 10 日记录。后者包含 GPU/进程快照、tags、运行模式、服务版本和 CPU 启动日志。

## 已完成的真实单题调用

2026-10-10 在 CPU 服务上，分别向两款模型提供题库原文 `zh-housing-2025` 和第一道事实题：“出租人应将住房租赁合同向哪个部门备案？”每次调用使用 temperature 0、seed 42、上下文 8192、单并发。

| 模型 | 真实答案 | 调用总耗时 | 执行设备证据 |
|---|---|---:|---|
| Qwen2.5 7B | 房产管理部门 | 63.149 秒 | Ollama `/api/ps` 的 `size_vram=0` |
| Llama3.1 8B | 租赁住房所在地房产管理部门 | 94.117 秒 | Ollama `/api/ps` 的 `size_vram=0` |

两次都返回实际 JSON 答案和引文。请求、完整响应、token 数、时长、题目与文章摘要保存在 `output/server-evidence/server-model-smoke.json`。这是接口功能检查，使用的简短提示并非平台统一测评提示，也没有校准置信度等字段；不能用这两道调用计算或宣称模型阅读能力排名。

2026-10-11 已恢复服务并检查 `/api/tags` 返回两个模型，CPU 启动日志确认 `inference compute id=cpu`。后续平台实验由应用服务执行，实验结果保留在 SQLite、JSON 和 CSV 中，详见 `verification.md`。

## 重启后的恢复命令

在服务器项目目录执行：

```bash
cd /home/jmy/reading-bench
bash deploy/start-isolated-services.sh cpu
```

脚本先启动平台，再启动专用模型服务，并检查两个端口；已有本项目tmux会话会保留。权重直接复用 `runtime/models`，不会重新拉取标签。服务器重启会结束tmux会话，需要执行此命令恢复；此项目没有配置系统自动启动。

本机另开终端运行 `powershell -ExecutionPolicy Bypass -File .\connect-server.ps1`，然后访问 `http://127.0.0.1:8877`。未来选择空闲GPU时，启动参数可改为其物理编号；脚本的显存、进程与CUDA检查必须通过。已有CPU会话不会因再次调用参数改变而自动替换，切换前需确认没有活动实验并单独停止本项目模型会话。
