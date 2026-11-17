# 模型与服务器部署计划

更新：2026-10-11。已按用户提供的服务器使用指南连接 `gpu-server`，应用部署到 `/home/jmy/reading-bench`，模型下载到其 `runtime/models`。本文包含实际环境的复现入口与通用备选方案；设备状态与完整远程实验以 `server-model-execution.md`、`verification.md` 的实测记录为准。

## 1. 首版结构与模型选择

平台为 Python 3.11+ 标准库 HTTP 服务、SQLite 和静态前端，入口是项目根目录下 `python -m backend.server`，默认端口 8787。题库来源文件在 `data/`，运行数据库/实验状态在 `var/`；Docker 用命名卷持久化后者。模型服务独立运行，平台通过 Ollama API 或 OpenAI-compatible API 发起真实请求。

首轮使用已有的 Qwen2.5 7B Instruct 与 Llama 3.1 8B Instruct 两个早期模型，固定权重摘要、量化和 prompt 后，用 2025 年以后首发且来源可核验的文章作时间隔离题库。

| 项目 | Qwen2.5 7B Instruct | Llama 3.1 8B Instruct |
|---|---|---|
| Ollama 名称 | `qwen2.5:7b-instruct` | `llama3.1:8b-instruct-q4_K_M` |
| 原始模型发布 | 2024-09-19，[官方公告](https://qwenlm.github.io/blog/qwen2.5/) | 2024-07-23，[官方卡](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) |
| 训练数据时间信息 | 本次查阅的[模型卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)未给出精确截止日 | 官方卡说明预训练数据截止 2023-12；这不是完整指令微调结束时间 |
| 中文实验含义 | 官方声明支持中文，可作首个演示模型 | 可作对照模型；语言支持和训练方案与 Qwen 不同，不能只把差异解释为参数规模 |
| 实际上下文计划 | 首轮共同设 8,192 tokens，单并发 | 同左；不根据原始模型最大窗口默认给出 128K 实验 |
| 版本策略 | 固定当前实际 digest 与模板；正式集前核对原始权重来源 | 同左；量化不是进一步训练，但量化可改变得分 |

本机已选模型的预期摘要（平台默认配置）：

```text
qwen2.5:7b-instruct
sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e

llama3.1:8b-instruct-q4_K_M
sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e
```

这些 digest 标识实际运行文件。服务器拉取后必须比对，不能自动以新 digest 覆盖旧实验。**digest 未变 + 早期发布日期不等于已经验证了全部训练历史。** 正式报告要保留原模型不可变 revision、量化来源和模型卡快照；污染控制细节见 [metrics-and-methodology.md](metrics-and-methodology.md)。

原始 Qwen2.5 模型卡的 128K 上限需要特定长文本配置；Ollama 实际窗口也由设置与资源决定。GPU 显存包括权重、KV cache、运行缓冲区和并发请求，实际占用与耗时见部署记录。

## 2. 实际服务器与部署步骤

用户指南中的 SSH 别名为 `gpu-server`，登录为 `jmy@10.50.2.29`。已核实主机 `qilin`、Ubuntu 22.04.5、256 GiB内存与约1.7 TB可用磁盘。2026-10-10只枚举到3张RTX 3090且CUDA初始化失败；2026-10-11服务器重启后4张卡可见、CUDA初始化成功，但每卡已有VLLM推理进程并占约9688 MiB，因此本项目仍使用CPU。资源随共享任务变化，不能沿用旧快照。本次模型端口为 `127.0.0.1:11435`，应用端口为 `127.0.0.1:8787`，采用原生Python与已安装Ollama，Docker方案留作备选。

服务器应用复现入口：

```bash
cd /home/jmy/reading-bench
bash deploy/start-isolated-services.sh cpu
```

该命令先启动平台再恢复模型服务，复用已下载权重。应用在专属tmux会话 `reading-bench-app` 中运行；模型会话为 `reading-bench-ollama`。下面步骤用于首次部署与复查，执行结果见验收记录。

1. 按用户提供的 SSH 配置名称/连接方式进行只读预检：系统、GPU/驱动、显存、RAM、磁盘余量、Docker 与已有服务。优先复用已安装的模型服务，不覆盖其他项目。
2. 根据实际资源选 Ollama CPU / NVIDIA GPU / 现有 OpenAI-compatible 服务。先单模型、单并发、8K 上下文；未验证资源前不同时驻留两个模型。
3. 将本项目放到独立目录，创建私有 `.env` 和独立数据卷；应用和模型端口默认只绑定服务器回环地址，通过 SSH 隧道演示。
4. 拉取/迁移需要的模型权重，记录 digest、Ollama 版本、chat template 和服务镜像。核对与冻结实验的一致性，补录原始 checkpoint/量化出处。
5. 运行健康检查、真实单题、无答案题、错误模型名、断开接口、重启持久化验证；记录实测延迟与 GPU 使用，之后再开始批量评测。
6. 现场演示前固定题库、模型和评分版本，运行一次完整演示，导出 JSON/CSV。远程部署完成后才记录“已部署”与服务器验证证据。

迁移到其他服务器时需重新核查系统、GPU、RAM、磁盘、SSH与已有服务。密码和私钥内容不在聊天中传递。更改Docker runtime或系统驱动会影响共享服务；本次原生部署未进行这些变更。

## 3. Linux 服务器：可执行的 Docker 方案

服务器需要已安装 Docker Engine、Compose 插件和 Python 3。NVIDIA GPU 路径另需可工作的驱动与 NVIDIA Container Toolkit；依据 [Ollama 官方 Docker 文档](https://docs.ollama.com/docker)和 [Docker GPU Compose 文档](https://docs.docker.com/compose/how-tos/gpu-support/)准备。

在 `reading-bench` 项目根目录执行。下列启动脚本仅启动应用/服务，不自动下载模型权重：

```bash
# 复用现有模型服务，或只先启动应用
python3 deploy/init_env.py
# 首次启动前编辑deploy/.env的READING_BENCH_OLLAMA_URL为服务实际地址
bash deploy/start-server.sh app

# 新建 CPU Ollama 服务（可运行但速度须实测）
bash deploy/start-server.sh ollama-cpu

# 或新建 NVIDIA GPU Ollama 服务
bash deploy/start-server.sh ollama-gpu
```

`deploy/init_env.py` 首次创建 `deploy/.env`，生成随机接入令牌，保留既有文件，默认模式 0600（Linux）。Compose 在令牌缺失时拒绝启动；容器应用绑定 0.0.0.0，宿主机仍只映射 `127.0.0.1:8787`。`/api/health` 可公开返回基础健康状态，其他接口需要 Bearer token。在平台输入 `.env` 中的令牌；不要把令牌加入截图、版本库或公开导出。

默认模型URL `http://ollama:11434` 适用于下面新建的Compose模型服务。仅启动app并复用外部服务时须先改URL。已有SQLite模型不会因修改环境变量自动更新；若曾以错误URL启动，可在模型管理新增正确URL的配置再选择它，当前没有模型编辑界面。

首次权重下载（CPU/GPU 二选一，需有足够磁盘和网络）：

```bash
bash deploy/pull-models.sh ollama-cpu
# GPU 方案用：bash deploy/pull-models.sh ollama-gpu
```

此脚本将下载两个模型并创建 `deploy/model-manifest.json`。文件已存在时不覆盖；再次运行需先核验清单，另选输出文件记录新版本。正式实验前不要重新 pull mutable tag。

冻结/核对模型：

```bash
python3 deploy/capture-models.py --url http://127.0.0.1:11434 --output deploy/model-manifest-initial.json
python3 deploy/capture-models.py --url http://127.0.0.1:11434 --verify deploy/model-manifest-initial.json
```

脚本从 [Ollama 列表 API](https://docs.ollama.com/api/tags)及 show/version API 保存模型 digest、大小、量化、模板和运行版本；校验不一致时停止。它不会把摘要未变描述为训练来源已认证。

默认镜像标签是启动材料，可能更新。部署验证后记录镜像并把 `.env` 的 `OLLAMA_IMAGE`、`PYTHON_IMAGE` 换为实际仓库的 `image@sha256:digest`；重新构建固定镜像用于正式实验。不要记录不存在的 digest。

```bash
docker image inspect ollama/ollama:latest --format '{{json .RepoDigests}}'
docker image inspect python:3.11-slim --format '{{json .RepoDigests}}'
```

### 接入现有 Ollama 或 OpenAI-compatible 服务

应用容器访问服务器宿主机时，将 `.env` 中 `READING_BENCH_OLLAMA_URL` 改为 `http://host.docker.internal:11434`；宿主机 Ollama 必须能够接受来自 Docker 网桥的请求。若其只绑定宿主机回环地址，容器无法连接，应采用下面的原生应用方案，或按服务器内网策略调整监听和防火墙。容器内的 `127.0.0.1` 指容器自身。

Ollama Compose 服务的地址是 `http://ollama:11434`。外部/另一个内网推理服务可在平台模型配置中添加可访问URL。OpenAI-compatible模型填写以 `/v1` 结尾的base URL。若服务需要密钥，先在应用进程的服务端环境中配置密钥，再用 `POST /api/models` 的 `api_key_env` 字段指定环境变量名称；当前界面没有该字段，需要通过API登记。密钥明文不写入模型配置、前端或实验导出。这条接入路径尚未用远程付费API实测。

## 4. 无 Docker：原生 Python 应用

复用已安装的 Ollama 时，标准库服务可以直接运行；下面命令只影响当前 shell。

```bash
cd /absolute/path/to/reading-bench
export READING_BENCH_HOST=127.0.0.1
export READING_BENCH_PORT=8787
export READING_BENCH_DATA_DIR="$PWD/var"
export READING_BENCH_OLLAMA_URL=http://127.0.0.1:11434
python3 -m backend.server
```

保持终端进程运行，或在服务器状况核实后配置systemd。上述回环地址示例无需令牌；应用绑定非回环地址时必须配置非空 `READING_BENCH_TOKEN`。若要启用令牌，在启动应用前生成并保存到权限0600的私有文件，用户自行读取并填入平台；长期运行应改为专属EnvironmentFile。临时export变量不会跨SSH会话保留，勿将令牌写进公开截图或导出。

## 5. 从本机安全演示服务器平台

本机当前校园WLAN与代理环境使用项目连接脚本，每次读取当前WLAN地址，通过逐连接中继连接用户已有SSH别名：

```powershell
powershell -ExecutionPolicy Bypass -File .\connect-server.ps1
```

浏览器访问 `http://127.0.0.1:8877`，保持终端运行。已实际验证该隧道与服务器健康接口。模型API无需转发到本机。其他网络下普通SSH能够连接时也可使用下面通用命令：

```powershell
ssh -N -L 8787:127.0.0.1:8787 YOUR_SERVER_ALIAS
```

随后本机浏览器访问 `http://127.0.0.1:8787`。如果本机 8787 已被占用，使用 `-L 8788:127.0.0.1:8787`，浏览器改 8788。无需公开服务器 8787 或 11434；不在本机与远程应用间误用令牌。

## 6. 持久化、备份和可验证交付

- SQLite/实验状态：Docker `bench_data` 命名卷映射 `/app/var`；原生方式存 `READING_BENCH_DATA_DIR`。应用重启后应保留已完成结果，中断任务标记中断并新建重跑。
- 模型：Docker `ollama_models` 命名卷；原生 Ollama 按其配置的模型目录。权重拉取不会写入代码目录。
- 源题库：`data/corpus.json` 及 `data/raw/` 的来源快照、许可、时间、hash 随交付归档；更新源题库后重建镜像。数据库已存在时的模型配置不一定被新环境默认值覆盖，需在界面核对 URL。
- 优先用平台导出 JSON/CSV 保留逐题结果。在线 SQLite 文件不能仅复制主 `.sqlite3` 而遗漏 WAL；做数据库备份应使用 SQLite backup API，或停止应用后完整归档运行目录。
- `docker compose ... down` 停止服务而保留命名卷；不要在需要保存实验时使用 `down -v`。恢复/清理另行按用户目标执行。

远程验收记录应包含实际服务器环境、服务健康响应、两个模型可用性/digest、至少一条真实模型回答、故障路径、一次重启后的结果仍在、实际完整实验导出和时间。尚未执行的项目标成“待验证”，不能用配置文件存在来替代远程验收。

## 7. 当前验证范围

实际部署采用Linux原生Python和Ollama，服务器应用健康、SSH隧道与11项关键测试已验收。两模型权重已下载并核对全层SHA256；GPU推理与平台实验见实测记录。Docker Compose与容器GPU方案尚未执行，不能据配置文件存在宣称通过。部署Python脚本的语法、随机token生成与已有文件保护、模型清单抓取、摘要/模板/运行版本核验及故意改变digest后的拒绝路径已另行检查。AMD、多GPU与vLLM高并发属于后续配置。
