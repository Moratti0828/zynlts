# Reading Bench：AI 阅读理解能力测评平台

课程《专业综合能力提升 / AI 原生工程实践》项目。金明源（20241060148），单人组，课程允许。仓库：[Moratti0828/zynlts](https://github.com/Moratti0828/zynlts)。

用固定文章和问题调用可定位模型，按题型/语言评分，保存原始回答、失败、版本快照和成本。本仓库包含可执行平台、开发题库、历史模型输出、课程工程材料和本轮自动验收证据。

**当前定位：可运行的开发测评平台。正式隐藏集仍未完成独立人工审核；双方结对挑战尚未实际完成。** 不据开发集发布正式模型排名。历史10月实验与2026-11-17本轮验证分开保存。

## 快速启动

需要 Python 3.11+，推荐3.12。macOS/Linux：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-tokenizer.txt
sh start.sh
```

打开 <http://127.0.0.1:8787/#demo>。`start.sh` 优先使用虚拟环境，也可用 `READING_BENCH_PYTHON` 指定解释器。基础页面/服务不需要额外Python库，精确输入预算和完整验证使用上述依赖。

Windows：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tokenizer.txt
.\.venv\Scripts\python.exe -m backend.server
```

**真实推理另需模型服务和正确配置。** 克隆仓库不会带入作者数据库、模型权重或冻结tokenizer，不保证立刻显示11个在线模型。可按[模型部署](docs/model-deployment.md)、[现场演示指南](docs/live-demo-guide-20261026.md)准备Ollama与模型；历史指南中的本机/服务器“已在线”是当时记录。严格预算还需按[历史README的冻结命令](README-20261026.md)准备匹配tokenizer。未匹配时明确拒绝或仅允许标注的开发估算，不能冒称精确认证。

## 无 GPU 的完整验证

还需 Node.js（CI用22）。以下命令不调用模型，使用临时数据库；输出目录必须不存在。

```sh
.venv/bin/python scripts/verify_course.py --output evidence/my-verification
.venv/bin/python scripts/compare_short_f1.py --output evidence/my-experiment
```

Windows替换为 `.venv\Scripts\python.exe`。课程验证执行Python测试、前端契约和历史证据SHA检查，保留日志、退出码、秒数和源码Hash。2026-11-17实测：97项Python测试无跳过、21项前端检查、103个历史证据文件通过；干净启动HTTP200。详见 [本轮验证](evidence/course-20261117/verification/verification.json) 与 [启动记录](evidence/course-20261117/startup-check.json)。GitHub Actions配置于 `.github/workflows/verify.yml`，实际状态以仓库Actions页面为准。

EXP-001比较保留的原F1实现与预测Counter复用实现，固定合成输入，三轮交替计时；所有逐项结果一致。本机中位耗时分别约16.38ms与12.95ms。只支持该微基准，不表示模型推理提速。协议、逐次输出和决定见[实验协议](docs/experiments/EXP-001-protocol.md)、[原始记录](evidence/EXP-001-20261117/result.json)、[ADR](docs/adr/ADR-002-f1-counter.md)。

## 评分项补强（2026-11-17第二轮）

新增[评分导航](docs/course/score-improvement.md)、[受限评价工作流](review/evaluator/README.md)、[变更与修复记录](review/change-002.md)及[8分钟答辩练习](docs/defense/walkthrough.md)。K1—K6公开样例及额外边界检查、4类内存故障检出/恢复、续跑/版本拒绝/重复请求演练都有原始记录；首次漏检也保留。本轮自组验证不能代替同伴交叉审查和个人现场考试。最新[完整验证](evidence/rubric-20261117/verification/verification.json)：105项Python测试、21项前端检查、103个历史文件核验及故障演练均通过。

## 课程交付入口

| 内容 | 入口 |
|---|---|
| 课程要求、完整性与表单 | [课程审计](docs/course/completeness.md)、[可复制表单信息](docs/course/submission-form.md) |
| 目标、计划、任务 | [Global](Global.md)、[Plan](Plan.md)、[Tasks](Tasks.md) |
| 需求与规约 | [问题框架](docs/course/problem-frame.md)、[规格](docs/specification.md)、[验收矩阵](docs/course/acceptance-matrix.md) |
| 工程规则与架构 | [Harness](Harness.md)、[ADR](docs/adr/ADR-001-runtime.md)、[状态模型](docs/course/state-model.md)、[影响分析](docs/course/impact-map.md) |
| 实现与证据 | backend/、frontend/、tests/、evidence/、output/；[仓库地图](docs/course/repository-map.md) |
| 对抗组与复现 | [双方挑战计划](review/peer-plan.md)、[Finding](review/findings.md) |
| AI与责任边界 | [使用披露与缺项](docs/course/ai-disclosure.md) |

对抗组为SparseVision-CLI（贾子钊、邹弘辉），双方属于异题结对。计划围绕困难样本路由比例/稀疏Token预算、边界输入、投影守恒和统计一致性。具体规则、权限与范围待双方确认；目前对方仓库不可读取，不声称已完成源码审查或伙伴复现。

## 历史实验与数据

10月历史开发记录包括10款基础模型/11配置、近期40篇320题及公开参考100篇章300题；两个扩展轮次记录合计3,926次调用，不能当作3,926道独立题。本轮只重新核查其中10月25日交付包的103个文件与一致性，没有重新执行GPU模型推理。

历史报告：[10月20日](docs/2026-10-20--reading-ability--r01--development-comparison.md)、[10月25日](docs/2026-10-25--reading-ability--r02--model-data-expansion.md)、[10月26日演示](docs/live-demo-verification-20261026.md)。历史环境和绝对路径属于捕获时信息。完整旧说明保留于 [README-20261026.md](README-20261026.md)，若与本页冲突，以本页当前状态为准。

数据来源/用途与污染边界见 [来源记录](docs/corpus-provenance.md)、[公开参考集](docs/public-reference-datasets-20261024.md)。公开材料及论文保留原来源与权利，不授予统一再许可。本项目不训练或微调模型。近期候选题的AI复核不算人审；正式隐藏集尚未冻结。

## 恢复与边界

默认仅监听127.0.0.1。远程监听必须提供 `READING_BENCH_TOKEN`，密钥通过环境变量管理。停止服务后备份整个 `var/`；不要提交SQLite、.env、模型和密钥。服务重启将未完成任务标记interrupted，v2显式续跑只处理未完成项；错误项仍在计划分母中。旧结果不覆盖、不伪造人工签署或伙伴结果。
