# 统计附录

{
  "group_by": [
    "source_bank_sha256",
    "model_id",
    "mode",
    "num_ctx",
    "language"
  ],
  "bootstrap_repetitions": 2000,
  "bootstrap_seed": 20261025,
  "confidence_level": 0.95,
  "generation_seed": 42,
  "generation_seeds_n": 1,
  "bootstrap_unit": "source_cluster_id within bank/language and actual selected cohort; whole clusters resampled",
  "pairing": "same canonical bank, language and identical article/question keys; intersection only",
  "context_policy": "Never subtract 4K-subset and 8K-full means; report paired intersection with excluded counts",
  "metrics": "Project-local normalization/character-word F1; not official SQuAD/CMRC leaderboard scores",
  "public_reference_evidence": "span-derived proxy, auxiliary only; no genuine reasoning-chain accuracy claim",
  "aggregation": "all planned applicable questions; errors zero; valid subset diagnostic only; missing task N/A",
  "statistics": "exploratory marginal percentile 95% cluster CIs; no tests, p values, multiplicity/winner claims",
  "small_cluster_policy": "fewer than two clusters: CI not estimated; degenerate finite-sample CI is not certainty",
  "limitations": "human review 0; public historical training contamination high/unknown; recent dates do not prove no contamination; provisional clusters; single seed"
}

## 抽样、分母与配对

每个bank、语言和实际选中来源簇集合使用固定种子，按source_cluster_id有放回抽取同样数量的簇，簇内适用题全保留。不同模型同一簇集合使用相同重采样索引；差值在精确同题交集上成对计算，重采样仅使用这些共同题的来源簇。没有把同篇多题当作独立重复。

比例/F1点估计按全部计划适用题求均值，失败记0；kind缺失分母0、值为N/A。每次bootstrap按抽到的全部适用题重新求均值，2.5%/97.5%分位构成探索性边际区间；effective_resamples记录有适用值的次数。若少于2个来源簇不估CI。cluster_mean_sd/cluster_difference_sd是来源簇差异，不是跨seed标准差。

CI不作多重校正、不具备家族整体95%覆盖；不计算p值、不声称显著或赢家。全对等有限样本可能产生退化区间，不代表总体不确定性为0。只有一次生成seed=42，公开参考训练污染高/未知，近期稿人审0；来源簇未经完整人工谱系复核。

所有模型对比是完整已提供分组的探索性枚举，不是新的预注册。窗口比较方向为较大窗口减较小窗口，且先取相同题交集；不同canonical bank绝不配对。某配置缺少无文/另一模型不自动补0；没有共同题则写unavailable_pairs，不直接减均值。

## 审计规则

只接受当前v2.2 runner及当前prompt/grader版本。逐矩阵核对stage计划（存在时）、source bank/selection canonical hash、完整model/mode作业、配置快照、模型digest/模板/分词身份、原题计划、全局run/attempt唯一、导出JSON/CSV SHA、CSV重建一致、原始有效响应解析及逐行重评分。全部job须completed+exported+complete；failed即使已填满也不视作完成。GPU声明必须有匹配run/model digest的设备观察。

来源hash验证只能证明快照一致，不证明网页真实性、全球最早发表、独立人审或训练非成员身份。归档输出和当前版本无条件等价也不因hash而成立。
