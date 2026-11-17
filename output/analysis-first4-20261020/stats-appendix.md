# 统计附录

{
  "unit": "source_article_cluster",
  "bootstrap": "language-stratified paired percentile cluster bootstrap; no domain/length sub-stratification",
  "repetitions": 2000,
  "bootstrap_seed": 20261020,
  "generation_seed": 42,
  "generation_seeds_n": 1,
  "temperature": 0,
  "confidence_level": 0.95,
  "hypothesis_tests": "none",
  "p_values": "not computed",
  "multiplicity": "marginal exploratory 95% CIs, not simultaneous; no significance/winner claims",
  "human_review_count_distribution": {
    "0": 20
  },
  "aggregation": "planned applicable item mean; errors zero; no unified reading score",
  "valid_subset": "supplemental diagnostics only; not a replacement for end-to-end planned denominator",
  "short_f1": "project-local character/word multiset overlap, not official SQuAD/LongBench score",
  "no_context": "only exact matched questions; all evidence metrics N/A; prior knowledge difference does not prove contamination",
  "efficiency": "wall latency includes scheduling/model loading/serialization; load_duration is unavailable, so no pure decoding latency is inferred; warm_proxy excludes only each run's first recorded item, not guaranteed stable hot state; throughput is observed output tokens divided by paired end-to-end wall seconds; hardware residency is sampled, not proof every request ran on GPU"
}

## 预定模型对比

方向为 left minus right；效应量为绝对比例差，乘 100 为百分点。以下为事先指定的比较族，不通过结果挑选对比：

- qwen25-3b minus qwen25-15b
- qwen25-7b minus qwen25-3b
- qwen25-14b minus qwen25-7b
- qwen25-7b minus mistral03-7b
- qwen25-7b minus internlm25-7b

所有模型对比只取 with_context；有文/无文对照先按 article_id、question_id 取相同配对子集，再计算各题型答案指标。无原文的证据、联合成功及理解总分均不纳入。

抽样方案：在每种语言内，从该语言 10 个独立 source_cluster_id 有放回抽 10 个簇，每次保留簇内所有适用题；同一重采样索引用于所有模型和条件。没有把题目当成独立样本，也没有进一步按领域/长度拆成几乎均为单例的层。2000 次百分位区间为 2.5%/97.5% 分位；若某次没有适用题，该指标该次为缺失，需看 effective_resamples。

报告点估计为全部计划适用题的均值；cluster_mean_sd 描述不同源文章簇的任务均值差异，并非多 seed 标准差。分母不等时，在每次样本中按抽取的适用题重新计算均值，而非把百分比当独立重复试验。

显著性检验：未进行。没有参数检验，因此不作缺乏依据的正态性/方差齐性断言。不生成 p 值，不宣称胜出。列出的边际 95% CI 未作多重校正，不具备家族整体 95% 覆盖率；五模型对比及两语言多任务均属探索性效应量。正式研究若需检验，应事前固定主指标、配对簇随机化/置换方案与 Holm 等多重校正。

人工审题 0、development、formal=false。原始资料来自固定 source bank，验证过呈现正文 hash、计划键、模型 digest、运行/评分/提示版本、原始响应与解析响应、尝试日志、CSV/JSON hash 和逐行评分。外部快照 hash 一致性不独立认证文章来源真实性或人类审题身份。

未完成的预定对比：

[
  {
    "left": "qwen25-14b",
    "right": "qwen25-7b",
    "reason": "Model unavailable in supplied complete matrices"
  },
  {
    "left": "qwen25-7b",
    "right": "mistral03-7b",
    "reason": "Model unavailable in supplied complete matrices"
  },
  {
    "left": "qwen25-7b",
    "right": "internlm25-7b",
    "reason": "Model unavailable in supplied complete matrices"
  }
]

完整效应量/区间见 paired-differences.json；来源路径和 SHA256 在 analysis.json 的 source_artifacts。
