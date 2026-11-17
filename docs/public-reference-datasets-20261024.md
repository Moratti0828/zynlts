# 公开历史阅读参考集 / 2026-10-24

本次增加两个官方开发集的确定性子集：SQuAD 2.0 dev（英文）与CMRC 2018 dev（中文）。它们用于检验真实抽取式阅读、答案别名及无答案判断，不替代近期自建题库，不进入正式隐藏测试。旧题与其维基百科来源极可能已被历史模型见过，因此统一标记`training_contamination_risk=high_or_unknown`、`split=reference`、`requires_temporal_isolation=false`、`formal=false`。运行必须明确选择开发/参考模式，并关闭不适用的时间隔离检查；禁止通过伪造近期发布日期使其通过时间门槛。

## 已接入的数据

| 数据集 | 完整原始context | 原始标题簇 | 本地题数 | 题型 | 固定数据文件版本 |
|---|---:|---:|---:|---|---|
| SQuAD 2.0 dev | 50 | 35 | 150 | 100短答、50原始无答案 | `240e165ab706d95bd4323653bb92421f446208cf`，2018-07-02 |
| CMRC 2018 dev，作者SQuAD格式转换 | 50 | 50 | 150 | 150短答 | `5c81039ef856de178b5198391b3cd40f4e5e8514`，2019-03-29 |

这里的100个context是**100个参考篇章，不是100篇独立近期文章**。SQuAD 2.0 dev完整原集只有35个维基百科标题；从同标题选取的篇章共用`source_cluster_id`，不将50个篇章当50个独立来源。CMRC子集按同样规则得到50个标题簇；两个集合共85个来源标题簇。两语言的题型与材料并不等难，不能直接把两集分差解释为语言能力差异。

每个原始context完整保留，没有根据答案裁剪或重写段落。一个context在本平台映射为一个段落ID（`p001`），这不意味着原始维基百科全文只有一段。`published_at`是固定数据文件提交日，有精确Git记录；它不是维基百科原文首发日，`first_published_at`保持null。CMRC原始2018列表格式不含答案偏移，本次使用作者2019年的官方SQuAD格式转换，直接保留其`answer_start`，不自己“修复”偏移。

## 官方来源与使用条款

- SQuAD 2.0官方数据：[固定dev JSON](https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/240e165ab706d95bd4323653bb92421f446208cf/dataset/dev-v2.0.json)。原文件4,370,528字节，SHA256为`80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8`。
- [SQuAD官网](https://rajpurkar.github.io/SQuAD-explorer/)明确注明数据集按 **CC BY-SA 4.0** 分发，已保存HTML快照及SHA。仓库`LICENSE`是**软件MIT许可**，单独保存，不能以此替代数据集及维基百科文本条款。引用：Rajpurkar, Jia and Liang, [Know What You Don't Know: Unanswerable Questions for SQuAD](https://aclanthology.org/P18-2124/), ACL 2018。
- CMRC 2018官方数据：[固定SQuAD格式dev JSON](https://raw.githubusercontent.com/ymcui/cmrc2018/5c81039ef856de178b5198391b3cd40f4e5e8514/squad-style-data/cmrc2018_dev.json)。原文件3,299,139字节，SHA256为`e9ff74231f05c230c6fa88b84441ee334d97234cbb610991cd94b82db00c7f1f`。
- [CMRC官方LICENCE](https://github.com/ymcui/cmrc2018/blob/c0eb1b6ba219847457e6af3180da722bbeb656af/LICENCE)为 **CC BY-SA 4.0**，已连同中英文README固定保存。引用：Cui et al., [A Span-Extraction Dataset for Chinese Machine Reading Comprehension](https://aclanthology.org/D19-1600/), EMNLP-IJCNLP 2019。

保留数据集作者与原始维基百科贡献者署名、来源及固定版本；分发改编数据时遵守CC BY-SA的署名与相同方式共享条件。本地改动仅为ID、元数据、答案别名去重以及证据代理映射，原文、问题、每条答案文字及原始偏移均保存。数据许可与项目代码许可分别处理。官网HTML是2026-10-24抓取的条款证据，其URL本身并非不可变版本；本地快照hash可以核对抓取内容。

## 抽样与质量检查

抽样种子为`reading-reference-20261024-v1`。先核验所有候选题的原始答案/干扰答案偏移，再按“数据集＋原题ID”的SHA选择题、按原始标题SHA轮流选完整context，优先覆盖标题，然后增加同标题篇章。SQuAD每篇预定2道可答＋1道原始无答案；CMRC每篇3道可答。选择只依赖来源内容、标签、哈希与预算，未查看任何模型输出或分数。

原集SQuAD共1,204个context、11,873题，答案偏移无校验失败；10个context因不足预定题型配额未入候选。CMRC官方转换共848个context、3,219题；176道原题至少有一条答案不能严格匹配其给定偏移，全部记录并从候选题中剔除，**不搜索替代偏移、不改答案文字**。113个CMRC context因此或因题数不足而不满足3题配额。最终所选300题的全部原始答案偏移均严格相符，原始文本、原题和原答案未改写。

所有300题都通过本平台schema检查与完整prompt的保守UTF-8预算：上下文8192、输出预留512、余量512；最大保守总量SQuAD为4,174、CMRC为5,349。没有发生context截断或答案偏移修复。预算仍为草稿估计，不能替代某模型原生tokenizer的严格认证。

## 评分解释

原始短答别名与无答案标签来自公开官方开发集，**本项目人工复核仍为0**，不能伪造为“双人审定”。选取的可答题按原始答案span机械映射至本地context段落；`evidence_annotation_origin=span_derived_proxy/draft`、`evidence_gold_status=unreviewed_proxy`，不把答案所在段当作已人工审定的完整必要支持链。一个context只有一个本地段落，证据定位本身区分度有限。

本参考集主要解释短答EM、项目字符/词F1、正确拒答和格式错误；证据成绩只作机械映射诊断，不用于宣称真实支持链质量或与近期自建集证据分数直接比较。这里使用平台的规范化和短答字符/词F1，**不是SQuAD或CMRC官方评测脚本，也不形成官方排行榜成绩**。CMRC原集没有无答案题，不对其填造拒答分母；无适用项应显示N/A。

## 文件与复现

- 导入脚本：`scripts/import_public_reference_20261024.py`。
- 固定原始资料与条款：`data/reference/sources-20261024/manifest.json`及同目录文件。
- 初始导入版封存在`data/reference/initial-import-banks-20261024/`；实际运行版为`data/annotation/reference-squad2-20261025.json`、`reference-cmrc2018-20261025.json`，不重复计篇章/题目。
- 完整检查清单、排除原题ID与文件/canonical hash：`output/public-reference-validation-20261024.json`。
- 映射测试：`tests/test_public_reference_import.py`。
- 前端离线状态/标签契约：`tests/test_public_reference_frontend.js`。

在项目根目录运行：

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.import_public_reference_20261024
.venv/Scripts/python.exe -X utf8 -m scripts.prepare_reference_execution_20261025
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_public_reference_import -v
node --check frontend/app.js
node tests/test_public_reference_frontend.js
```

原始文件缺失时可明确传`--fetch`下载固定官方文件。已有文件hash不符时拒绝覆盖；不追随最新数据、不静默修复原始标注。公开参考题库、近期开发题库和未来隐藏测试需保持独立计数与结果报告。

## 2026-10-25 完成核验与界面说明

实际提交前发现SQuAD同一Wikipedia标题簇跨不同篇章长度层，平台创建时拒绝（HTTP400，未保存run、未调用模型）。初始导入版本原样移至`data/reference/initial-import-banks-20261024`，拒绝manifest保存在`output/reference-admission-rejection-20261025`。新`reference-*-20261025`执行版只调整分层元数据：同标题含多种长度时统一`mixed_within_title_cluster`，并保留每篇`original_passage_length_bin`。原文、原题、答案、offset与span代理完全不变，标题来源簇也不拆分；这避免把同标题篇章伪装独立样本。SQuAD有16个篇章受分层标签调整，CMRC无混合标题。两集实际平台evaluate空响应准入及原字段往返回归已通过；最终hash见`output/reference-execution-validation-20261025.json`。

4K子集在模型推理前按固定SHA顺序和完整篇章保守预算选取，每集8个不同标题簇、24题；Qwen7B与Yi1.5-6B在相同题上各跑有文/无文。它们是原参考集的子集，不是新增16篇独立材料。Yi保留registry模板，原生4096，分词模板等价尚未认证。

8项公开导入映射测试通过，涵盖原始偏移不修复、原文/原题/答案不变、重复context、共享标题簇、确定性抽样、无答案标签、证据代理不能升级为人审金标，以及roundtrip发现问题被改写。真实300题再次完成原始记录roundtrip，两个题库文件SHA保持不变：SQuAD `c3262384deb97e331d1abb294cf3ce2136fd8a9c4a8e6d5eeb1665a292e28284`，CMRC `d74cf3bb8b4a33abe79c5b2f1961f011603f7b5c5cc42a19f0df8cd96d26ab1c`。

前端已按`annotation_origin=external_public_benchmark`区分“公开历史参考”和AI开发草稿：题库下拉、运行确认、文章日期、参考答案、历史列表及结果页都保留这一身份，提示可能已训练见过、本项目未独立复核。证据EM/F1标作代理证据，原始答案span映射只作辅助，不称人审支持链。

切入公开参考题库会默认关闭时间门槛；切回近期题库恢复开启，并重置未审定数据的运行确认。选题库尚未加载完成或ID不一致时不可创建实验，避免误用上一份题库的设置。

运行条件新增显式4096/8192上下文窗口，模型选项和模型管理显示已登记的原生上限。选择4K模型时表单降到4096、禁用8192并立即更新说明；提交时保存`num_ctx`，不会静默截断。移除4K模型后不擅自升回8K，可由操作者显式选择。**本参考题库只通过8192草稿预算；4K模型不能据此假定整库可运行。**应事前固定预算兼容的完整篇章子集或先认证精确tokenizer，不按答案裁剪原文。

`node --check`通过，7项无浏览器/无联网的前端契约检查通过：公开/近期切换时间开关、4K模型降窗与显示、加载期间禁止创建、公开材料/结果标签、证据代理说明、提交的4096窗口快照。未在本子任务调用模型、连接服务器或操作浏览器；实际部署与浏览器验收由主任务统一完成。
