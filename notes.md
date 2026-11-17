# 2026-10-26 现场演示联调

- 用户要求可投屏现场直接真实运行，优先建设独立#demo流程，保留旧题库、配置与历史评分。
- 工作分工：backend/live_demo与server路由；frontend演示交互/样式；重复启动入口/指南。root统一部署与真实调用，不让worker并行干扰GPU或服务。
- 验收区分连接诊断（0模型调用）与真实推理；错误结果保留，不用固定输出或历史结果冒充本轮现场执行。
- 最终：95项Python测试、21项前端离线契约、JS语法和PowerShell5.1/7启动检查通过。服务器仅空闲更新项目app，先作一致性备份，Ollama和他人GPU任务不动。server11配置/local2配置、4预设均可检查，最终无active且ready。
- 真实新运行：本机run-3c2034d26172中文1题8.800秒、run-48c1d48d99b4英文1题1.920秒；server API run-61df87c2a21f中文3题7.209秒；实际浏览器按钮run-803e05d88cc8中文3题6.536秒。合计8次真实请求，0格式/传输错误；仅作执行链路验收，非模型能力新排名。
- 浏览器10月26日已可用。实际点击、3/3结果、刷新同ID、页面JSON下载与API导出逐字节一致；当前截图output/live-demo-20261026/live-demo-server-completed.png，已检查真实布局，控制台error空。上轮浏览器不可用记录保留为当时状态。
- 三位worker主要功能落盘后受用量限制，root修复剩余恢复逻辑、测试fixture、busy入口并完成验收；未改旧题库/评分/实验。上轮交付103个源/产物hash再次只读检查通过。
- 启动入口launch-demo.ps1（默认Server，-Local本机），指南docs/live-demo-guide-20261026.md，验收docs/live-demo-verification-20261026.md，结果output/live-demo-20261026/。
- 资料同步遇到Windows文本CRLF校验行在Linux被当文件名后缀，校验先拒绝且未提取。校验文件改为显式LF字节后重传，运行服务/旧结果不受影响。

# 2026-10-25 本轮交付完成

- 已完成13matrix、23run、1862条真实调用，218条契约错误保留计零；所有JSON/CSV/hash/身份/逐题评分及GPU观察审计通过。结合10月20日2064次为两轮3926次，不是独立题量。
- 当前10基础模型11配置；近期去重40篇320题（中英各半），公开参考100篇章300题，参考与近期、合成分开统计；AI复核不等于人审，人审仍0。
- 83项Python测试与7项离线前端契约通过，HTTP核对11模型可用、40篇工作台计数、部署JS hash；48个服务器源文件hash匹配。app恢复和SQLite一致性备份完成。最终浏览器重验被Work设置禁用，未绕过，使用上述HTTP/离线验收并披露。
- 完整分析在output/analysis-expansion-20261025，两张真实结果图已逐图检查；报告docs/2026-10-25--reading-ability--r02--model-data-expansion.md，交付索引output/delivery-expansion-20261025.json。下文保留执行期间记录。

# 2026-10-20 多模型实验记录

## 已知依据
- 用户提供的 2026-10-10 使用指南只作为连接和资源说明；当前 GPU 必须重测。
- 上轮 2026-10-13 CUDA cuInit=999，完整文段 CPU 请求超时；原有 Qwen2.5-7B 和 Llama3.1-8B 位于 `/home/jmy/reading-bench/runtime/models`。
- 现有 v2 平台支持冻结题库、逐题原始结果、分语种报告、取消/续跑和无原文模式；20 篇开发选文目前只是暂选，需实质增加可执行题。

## 本轮观测
- GPU0真实CUDA初始化成功，Qwen29层全GPU，/api/ps size_vram=5,341,542,400字节；首载32.03秒，短答生成0.016秒，不作为阅读性能均值。
- 专属app8787/Ollama11435已在tmux恢复，本机8877隧道已核验。
- 7模型计划：Qwen2.5 1.5/3/7/14B、Mistral7Bv0.3、InternLM2.5-7B、Llama3.1-8B，统一Q4_K_M；仅Qwen系列认证原tokenizer，其他保守草稿预算。
- Ollama registry manifests已在下载前保存固定SHA；InternLM官方GGUF revision8fa9dff166b63e3d356b3a3ca95c5ab2a4b1b378（2024-07-16前已有）Q4_K_M文件SHA450ef0b157ee10586bb8fce4c5173ae1799345c43c537a6a7353518df1079f55。
- 新增权重仅下载到项目runtime/models，不触碰公共目录。预计新增约21GB，实际磁盘后续统计。
- 20篇160题文件冻结SHA ea4033e6d9e4b3052871eed683a7e65c280d1e4ac265ac1ef2a9807083b2ac3a；独立AI逐题内容复核未看受试输出，修正泄漏/跨题指代/最小证据与别名；human0。
- InternLM官方GGUF镜像约1MB/s，固定文件尚未完成校验，已停止本项目该下载并保留部分块。本轮改为同一Ollama Q4_K_M分发政策的非1M `internlm2:7b-chat-v2.5-q4_K_M`，下载前固定manifest aa0c9b808286311ca91e6c5f200f77be95b7c7c1428211d4fbb791358e02d06b。其blob与官方GGUF字节不同，不宣称两者相同；和其他Ollama模型一样保留转换链未独立复现限制。原作者GGUF仅作元数据对照，不能写已成功导入或已验证完整权重。
- 10个额外合成数字改文题在data/diagnostics，明确synthetic=true；每语种5题，源簇沿用原20篇，禁止计为新增真实文章或混入主成绩。
- 后续官方HF拉取模板失败但完整GGUF已缓存。独立解析291个tensor：官方完整SHA450ef0...正确；当前registry有226个量化payload和3项tokenizer元数据不同，因此不能认证等价，也不证明新训练/污染。已将官方完整2024 GGUF导入新ID internlm25-7b-official2024，manifest9ca68ac94adb81795241ed162c328cd6a5c8b6ec2620107c9f0b9c429e3e1245，实际日期门槛采用该固定GGUF已存在的2024-07-16。两者分开比较，旧记录未替换。
- 首4配置严格审计结果显示选择题接近满分，但数值/证据/拒答差异很大；不得只凭选择题或合成总分排名。Qwen7B中文严格证据12/60，事后统一ID格式敏感性诊断44/60，32题差异来自ID表示；辅助结果不替代主成绩。
- UI已将合法替代支持链分组显示，明确“任一组完整支持链均可”；合成文本范围显示“合成改文诊断”，评分与既有冻结记录未变。
# 2026-10-25 模型与数据扩展执行

- 新增Gemma2 9B/Phi3.5 mini/Yi1.5 6B的固定Q4_K_M模型，完整blob核验通过，总10基础模型11配置；GPU0属于其他项目，自有Ollama转GPU1，不影响他人。权重仍只在服务器项目目录。
- 近期新增20篇160题，中文/英文独立AI复核80题/语言，源文192段对齐；首次推理前修正8项实质金标/前提问题及名称别名/支持链，不据模型结果改金标。新bank canonical67f918724560f34c140c7464d39480b4c651a73754ef260a77f264bad8e0d9e3。两近期bank去重40篇320题；collection40只是视图。
- SQuAD/CMRC各50完整参考篇章150题，原题原文答案offset固定；35/50标题簇，不等于100独立近期文章。首个SQuAD创建因同标题跨长度层HTTP400拒绝且未建run、未推理，旧导入封存，执行版20261025只统一混合长度簇的层标签并保留原长度。CMRC原始有176题含不匹配offset，筛选排除，不伪造修正。
- 当前版本runner v2.2增加显式4K/8K/原生上限及公开集时间关闭门槛，prompt/grader不变。旧v2.1只读分析白名单可重审，混批/跨版本续跑仍拒绝。页面标签/默认切换/4K窗口已实际浏览器核对；优先选Qwen7B作为默认，避免默认混入4K模型导致旧长文超预算。
- 5stage/13matrix/23run目标1862调用：bridge500+reference600+Yi配对192+recent320+anchor250。anchor在查看新模型答案/证据成绩前追加（已可见运行状态和错误计数），以同runner/GPU复测Qwen7B；不称原始预注册。旧2064次单独封存。
- 已有82项Python单元测试+7项离线前端契约检查通过；随后又增加计划外matrix拒绝测试并单独通过（扩展9项）。真实推理未完成前不产完整分析结论。子代理用量受限后由root接手审计/报告。
- 新分析脚本scripts/summarize_expansion_20261024.py仅接受完整同v2.2资料，按bank/窗口/语言/模型分组，同题交集配对，2000簇bootstrap；公开span证据只辅助。finalize/finish脚本仅在全部stage完成和无active后重启项目app、更新工作台40篇计数并一致性备份。

# 2026-10-20 完整开发矩阵交付

- 28个run均completed：1280有文、640无文、80合成改文、64工程回归，共2064条真实响应与2064个全局唯一attempt。270条契约错误保留；主分析1920条中257条，非传输故障。完整JSON/CSV/hash/计划/身份/逐行评分/非空原始输出全部复核。
- 7款基础模型8配置（InternLM registry与官方2024 GGUF分开），主/无文/改文run均有全GPU驻留采样记录。最终空闲探针显示4卡均0%利用率，模型按keep_alive卸载；app/Ollama两个tmux继续运行。
- 核验入口：output/delivery-20261020.json；报告：docs/2026-10-20--reading-ability--r01--development-comparison.md；主分析与2张实数图：output/analysis-20261020。辅助格式诊断和合成改文不覆盖冻结主成绩。
- 数据库已一致性备份到服务器runtime/deployments/20261020/bench-final.sqlite3；报告、分析源与产物已同步服务器项目目录。最终runtime探针health=ok/1.2.0，Ollama0.13.5，磁盘约1.79TB可用，没有额外模型调用。
- 题库20篇160题仍人审0；候选402篇、合成10例和正式100篇隐藏测试不混计。来源簇暂定、单seed、非Qwen tokenizer未严格认证，不能发布正式排名或声称无污染。
- 交付审计脚本初次把成功attempt状态拼作recorded，实际后端为recorded_response；按backend/experiment_v2.py定义修复后全量审计通过，未改原实验。

