# 图目录

所有图由真实密封矩阵导出生成，不使用示例数字；PDF 为矢量版，PNG 为预览版。模型按输入注册顺序显示，不按得分排序。

## figure-01-task-comparison

- 文件：figures/figure-01-task-comparison.pdf / .png。
- 来源：numeric-table.json 中 with_context、question_kind=all 的 choice_accuracy、short_token_f1、numeric_strict_accuracy；所有原始导出及 hash 见 analysis.json。
- 用途：比较同一开发题集上中英文各答案任务的端到端表现。
- 图注：各语言 10 个源文章簇；每模型一次 seed=42；点旁为适用题数；误差线是 2000 次配对簇 bootstrap 的边际 95% CI；人工审题 0。
- 观察要求：必须同时对照点估计、区间和题数；N/A 不绘点。
- 决策作用：据题型差异选人工复查和后续补样方向；不得只凭点估计命名胜者。
- 局限：单 seed、小簇样本、开发题稿；短答 F1 不是官方 SQuAD/LongBench 分数。

## figure-02-context-difference

- 文件：figures/figure-02-context-difference.pdf / .png。
- 来源：paired-differences.json 中 comparison=with_context_minus_no_context_paired_subset。
- 用途：检验取得原文后，在相同题目上的答案差值。
- 图注：单位百分点，有文减无文；格内有配对题数；每语言 10 源簇；无该题型标 N/A；详细 CI 另见 JSON。
- 观察要求：以 0 为中心读方向，不能将极小分母的极值解释为稳定效应。
- 决策作用：负差及高无文正确率的样本优先复核提示、答案别名、知识可猜测性及早期来源。
- 局限：无文回答可能来自推断/常识/猜测；不能把该差值视为污染检测器或因果训练诊断。
