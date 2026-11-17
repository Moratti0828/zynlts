# 扩展矩阵离线审计与分析协议

本协议只分析本轮`output/expansion-20261024`的完整导出，不启动模型、不连接服务器、不修改金标或旧结果。实现为`scripts/summarize_expansion_20261024.py`，版本`reading-expansion-analysis-v1-20261025`。

## 运行

尚未拷回全部导出时，仅查看只读进度：

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.summarize_expansion_20261024 --matrix-root output/expansion-20261024 --output-dir output/analysis-expansion-20261025 --expected-stages bridge reference recent yi anchor --allow-incomplete
```

完整分析与实际绘图使用已有bundled Python，推理venv不额外安装绘图依赖：

```powershell
& 'C:/Users/13412/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -m scripts.summarize_expansion_20261024 --matrix-root output/expansion-20261024 --output-dir output/analysis-expansion-20261025 --expected-stages bridge reference recent yi anchor
```

默认bootstrap 2000次、统计种子20261025，生成设置仍是temperature0/seed42/512输出。`--skip-figures`可显式生成纯文本/数值包；不会假装已经画图。输出目录已有不同输入、统计参数或绘图选项的封存包时，必须使用新目录，避免将新结果盖在旧图上。

实际有限计划现为5个stage、13份matrix、23个run、1862条模型调用。anchor为在查看新模型答案/证据成绩前追加（当时已能看到运行状态与错误计数）的同批Qwen7B基线（160有文/80无文/10改文），不能称原始预注册。公开参考实际运行`reference-*-20261025`：仅修正同标题跨长度分层的元数据，原题原文/答案/offset不变；初始导入和首次无推理的HTTP400拒绝保存在矩阵目录之外。读取目录中若出现未列入现存stage计划的matrix会拒绝分析。

退出码0为完整成功，或显式`--allow-incomplete`下的只读进度；退出码2为资料未完整或完整性错误。allow-incomplete不能豁免hash/身份等错误，也不会建立输出目录或写结论。已有旧报告不会在缺数据时被删除或覆盖。

## 完整性准入

1. 递归发现matrix `manifest.json`；若有`*-plan.json`，核对其每个预定目录及bank、模型、mode、窗口、题目筛选和生成设置。`--expected-stages`要求指定stage的计划也必须存在，防止尚未创建stage计划就误称整轮完成。没有stage计划时，只能说完整分析了实际提供的矩阵，不能推断未提供的计划已经完成。
2. 复用现有选择/身份/CSV/逐行评分函数，验证source bank canonical、operator快照去装饰后hash、selection及其hash、计划投影、唯一question key、模型digest/模板/tokenizer身份与当前v2.2 runner/prompt/grader版本。
3. 核对JSON/CSV文件SHA、CSV从JSON重建一致、逐行原题/语言/题型/正文SHA、attempt与结果对应、有效原始响应解析一致、全部指标重评分一致。检查全局run ID和attempt ID唯一。
4. 每个job必须`status=exported`、`complete=true`，run必须`completed`且计划全记录。`failed`即使行数填满也不能作为完成分析。格式/契约失败是完整结果的一部分，留在计划分母并记零，不重答删除。
5. GPU/full-GPU声明须有匹配job、run、模型名和digest的设备观察。没有观察不补造执行证据，观察本身只代表采样到的驻留状态。

一致的hash能验证保存内容与导出契约，不能独立证明网页真实性、全球最早发表、原权重转换谱系、训练非成员或真实人审身份。

## 异质数据分层

分组键为`source_bank_sha256 + model_id + mode + num_ctx + language`。同一文章不同bank canonical、4K与8K、公开参考与近期稿均不合并总分。各组同时报告实际选中文章/来源簇/题型/维度/运行数，不能把完整source bank的题量当作当前run已经执行的题量。

- 近期题稿：AI编题，当前人审0，证据支持链也是开发金标。
- SQuAD2/CMRC历史参考：公开原答案保留，但训练污染高/未知，关闭时间隔离。原context是参考篇章，不自动当作独立上游百科文章；同一原题标题共享来源簇。
- 公开参考的证据为answer-span派生的代理；输出名为`span_proxy_evidence_em_aux`与`span_proxy_evidence_f1_aux`，角色`auxiliary_span_proxy`。它不构成真实推理链测量。
- 合成诊断：独立bank和track，不增加真实文章数量、不并入近期主指标。

短答EM/F1使用本项目规范化及中文字符/英文词重叠，不能写成SQuAD/CMRC官方榜单成绩。缺失题型/无适用题分母0，指标N/A；单语言题库不伪造另一语言分数。valid-output子集只辅助，不能替代端到端分母。错误响应也可能让误拒答/实质误答率为0，须同时看正确拒答、错误率和覆盖。

## 配对与统计

所有差值都先取同一canonical、语言、article_id/question_id的交集：

- 同模型、同窗口的有文减无文，仅比较匹配题目；无文证据不适用。
- 同模型、同mode的较大窗口减较小窗口，仅比较共同题。禁止把8K全量均值直接减4K子集均值；每项保存两侧全量、共同题及排除数。
- 同bank/窗口/语言下不同模型的有文差值，只用共同题。自动枚举的模型配对标为探索性，不伪称预注册。没有共同题只记录不可配对原因。

按实际选中来源簇在bank、语言内有放回抽取，簇内全部适用题保留；相同簇集合使用相同固定重采样索引，成对差值使用共同题的来源簇。不得把同篇多题当独立重复。少于2簇不估CI；全对等有限样本的退化区间不代表总体没有不确定性。

2000次百分位边际95%区间未作家族多重校正。只跑一个生成seed，不估跨seed方差，不作p值、显著胜出或总体排名声明。来源簇仍是当前分组定义，非人工认证谱系。

## 产物和图

- `numeric-table.csv/json`：分题型完整指标、分母、簇数、CI、有效输出辅助值和证据代理标记。
- `paired-differences.csv/json`：精确同题配对差值、两侧窗口/模型/条件和被排除数量。
- `wrong-cases.json`、`error-types.json`、`efficiency.json`：原始错例/契约错误和端到端p50/p95/观察吞吐；耗时含加载、调度与序列化，不能叫纯解码速度。
- `metadata.json`、`analysis.json`：来源清单、完整模型快照、运行设备、每组覆盖、版本、统计协议和不可配对项。
- `analysis-report.md`、`stats-appendix.md`、`figure-catalog.md`、`bundle-manifest.json`：由完整真实输入生成，最后一个列产物/来源SHA。
- 图1按bank、窗口、语言独立面板显示任务得分/题数；图2只显示4K条件下精确同题的有文减无文。缺适用配对就不画该图，不用示例数字补齐。图仅为描述，CI详表另列。

## 验证范围

`tests/test_expansion_analysis.py`的9项测试使用进程内假API，覆盖JSON篡改、不完整时无输出、计划外矩阵拒绝、填满但failed拒绝、bank/context隔离及同题交集、公开证据代理/缺题型N/A、GPU声明必须有证据、全局attempt唯一、封存产物hash。它们不是模型能力实验，也不计入真实调用次数。

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_expansion_analysis.py -v
```

CLI初版交付时只有只读进度与8项测试证据。最终已拷回完整13matrix/23run/1862条导出，通过全量准入审计，生成output/analysis-expansion-20261025完整分析包，两张实际结果图已逐图检查；新增计划外矩阵拒绝测试后，扩展分析9项、全项目83项Python测试及7项前端离线契约通过。完整报告见docs/2026-10-25--reading-ability--r02--model-data-expansion.md，实际hash及调用数以output/delivery-expansion-20261025.json为准。
