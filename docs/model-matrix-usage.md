# 可恢复多模型测试与离线分析

本轮为开发诊断，全部160题人审数为0。主题库包含20个独立源文章ID，中英文各10篇80题；不代表100篇隐藏正式测试已经完成。Qwen2.5四个规模、Mistral7B v0.3、Llama3.1-8B和InternLM2.5-7B，共7款基础模型；InternLM另保留两个分发配置，合计8个配置。

## 服务器与入口

- 项目：`/home/jmy/reading-bench`；权重：`runtime/models`，不使用公共模型目录。
- 平台：`127.0.0.1:8787`；自有Ollama：`127.0.0.1:11435`。
- 本机运行 `./connect-server.ps1`，保持终端打开，再访问 <http://127.0.0.1:8877/#v2experiment>。SSH断开不停止服务器tmux实验。
- 使用GPU0单模型、单请求并发，统一Q4_K_M、temperature0、seed42、8192上下文、512输出。`device-observations.jsonl`保存每个run期间采样到的显存驻留。
- Qwen使用冻结官方tokenizer和原生raw模板，并记录逐请求实际输入token核对。其余模型是保守字节预算＋实际token上限检查，未获得严格tokenizer等价认证。整体均为草稿模式，不能标为正式实验。

## 运行示例

在服务器项目目录执行；以下输出目录如果已有manifest，会按相同配置接着检查/导出，不重复完成题。

```bash
.venv/bin/python -u -m scripts.run_model_matrix \
  --base-url http://127.0.0.1:8787 --ollama-url http://127.0.0.1:11435 \
  --models qwen25-15b qwen25-3b qwen25-7b llama31-8b \
  --bank dev-expanded-20261020 --modes with_context --strict-budget false \
  --poll-seconds 10 --output-dir output/model-matrix-20261020-main-first4
```

无原文对照在每篇只取预先固定的q01—q04，共80题；不是与160题全量均值直接相减，离线分析先匹配相同题再计算差值。

```bash
.venv/bin/python -u -m scripts.run_model_matrix \
  --base-url http://127.0.0.1:8787 --ollama-url http://127.0.0.1:11435 \
  --models qwen25-15b qwen25-3b qwen25-7b llama31-8b \
  --bank dev-expanded-20261020 --modes no_context --question-ids q01 q02 q03 q04 \
  --strict-budget false --poll-seconds 10 \
  --output-dir output/model-matrix-20261020-diagnostic-first4
```

后3模型的ID为`qwen25-14b mistral03-7b internlm25-7b`。来源核验后的官方2024 GGUF使用独立ID `internlm25-7b-official2024`，不能覆盖registry版或混写成同一组结果。两个InternLM配置之间的量化/分词/模板差异也不代表重新训练或数据污染，详见`output/internlm-gguf-provenance-20261020.md`。

`run_initial_matrix_20261020.py`、`run_remaining_matrix_20261020.py`和`run_official_internlm_20261020.py`是本轮已明确条件的顺序包装器；不要用同名tmux会话重复启动并行控制器。每份输出目录都含manifest、原始JSON/CSV和设备观察。

## 中断与错误

- manifest在创建POST前保存意图，丢失创建响应会停止并标`creation_unknown`，不盲目重发。确认既有run ID后用`--reconcile model__mode=run-...`恢复跟踪。
- GET网络错误可安全重连。`interrupted/cancelled`只续未完成项；完整错误项不重试，仍留在分母。
- 版本、模型digest、正文/计划hash变化会拒绝混用。fatal失败需修复根因后显式`--resume-failed`；未知在途请求可能重复时仍保留attempt日志。
- 命令退出码1可以表示完整执行但存在已保留的模型/格式错误，不等于没有跑完；退出码2表示完整性、身份、连接或准入问题，需要检查日志。

## 分析

在本机使用带matplotlib/numpy的bundled Python，或自行安装相应独立分析环境；不在推理venv额外安装绘图库。将服务器完整matrix目录复制回来，运行：

```text
python -X utf8 -m scripts.summarize_model_matrix --matrix-dirs [六个主/无文矩阵目录] --expected-models qwen25-15b qwen25-3b qwen25-7b llama31-8b qwen25-14b mistral03-7b internlm25-7b internlm25-7b-official2024 --output-dir output/analysis-20261020
```

六目录分别是`main-first4`、`diagnostic-first4`、`main-last3`、`diagnostic-last3`、`official-main`、`official-diagnostic`，均带前缀`output/model-matrix-20261020-`。pilot16不能混入，合成改文也单列。缺数据时`--allow-incomplete`只输出进度，不制作图或结论。

分析检查来源hash、版本、模型、计划键、原始响应、attempt日志、JSON/CSV hash及逐行评分。中英文/各题型分别给主要指标，使用语言内源文章簇配对bootstrap2000次；仅单seed、每语言10簇，不做显著性排名。有效输出子集、耗时和事后证据ID格式归一化只作辅助，不能替换端到端计划分母。

`diagnose_evidence_id_format_20261020.py`只诊断方括号/首尾空白/唯一短段ID造成的影响；不修复失败回答、不改变主分数。`summarize_counterfactual_20261020.py`另核对10个合成数字改文与原题的严格/辅助数值结果，不将合成案例计作新增真实文章。
