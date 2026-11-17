# LLM 阅读能力评价：论文与官方评分实现核查

检索与核查日期：2026-10-13（北京时间）。本文件是方法综述，不是已执行模型实验的成绩表。来源优先采用 ACL、ICLR、PMLR 原论文和作者／机构评分代码；下文“已读”指读过所列方法、评估和实现部分，不表示逐页全文精读。

## 结论与对现有方案的修正

**学术界没有一个已经公认、跨语言和跨任务通用的“LLM 阅读理解总分”。** 本次核查的基准采用不同任务和评分协议：短答常用 EM / token F1；选择题用 accuracy；多跳问答增加支持事实及联合分；开放答案使用参考答案、rubric、人工或模型裁判。长上下文长度、证据定位、无答案识别也需要分项报告。

项目此前提出的六维能力划分、五维等权平均、按文章宏平均、段落集合严格匹配以及可回答性平衡分，都是**本项目的操作化设计**。它们有研究动机，但不是某篇论文已验证的标准量表，不能直接称为 PISA 分数、HotpotQA 官方分数或普遍适用的学术排名。论文比较需要使用原数据、原版本和原 scorer；仅使用相似公式不构成成绩可比。

## 已读的一手来源及实际指标

| 基准／论文、正式发表年份 | 任务与语言 | 实际使用的评分 | 本项目应借鉴的内容与局限 | 已读证据位置 |
|---|---|---|---|---|
| [RACE，EMNLP 2017](https://aclanthology.org/D17-1082/) | 来自中国英语考试的英文四选一阅读题；词匹配、释义、单句和多句推理 | 选项 accuracy，报告 RACE-M / RACE-H 等子集 | 题目在中国编制不等于中文题库。四选一有 25% 随机基线；仍受选项线索和考试体裁影响 | 已读 PDF §3.2、§5 和 Table 5 |
| [SQuAD 2.0，ACL 2018](https://aclanthology.org/P18-2124/) | 英文段落抽取式问答，加入与文本相关且存在诱饵的无答案题 | 规范化 EM 和 token F1；无答案题正确弃答两项均为 1，否则 0。论文在开发集确定拒答阈值后应用于测试集 | 分开报告可回答／无答案题，拒答阈值只能在开发集调。简单无关问题不等价于困难无答案题；短答重合指标不检验完整推理 | 已读 PDF §5.1–5.2、Table 3及脚注3；本次未成功通过搜索工具打开原官方脚本 |
| [HotpotQA，EMNLP 2018](https://aclanthology.org/D18-1259/) | 英文 Wikipedia 多跳问答；提供支持事实句子；distractor / full-wiki 两种设置 | Answer EM / F1；Support-fact EM / F1；Joint EM / F1 | 证据采用 `(文章标题, 句子序号)`，是句级集合。能检验答案及支持事实的输出一致性，但不能证明内部推理忠实 | 已读 PDF §5.2；[作者 scorer](https://raw.githubusercontent.com/hotpotqa/hotpot/master/hotpot_evaluate_v1.py)完整相关函数 |
| [DROP，NAACL 2019](https://aclanthology.org/N19-1246/) | 英文段落上的离散推理：加减、计数、比较、排序等 | EM 和 numeracy-aware F1，多答案取最佳匹配；多跨度答案进行对齐 | “找到数字”不是离散运算。数值评分不能照搬普通 token F1。论文说明与当前机构实现存在细节差异，应固定实现 | 已读 PDF §5；[AllenAI scorer](https://raw.githubusercontent.com/allenai/allennlp-models/main/allennlp_models/rc/tools/drop.py) 的 `get_metrics`、数字门控和对齐 |
| [NarrativeQA，TACL 2018](https://aclanthology.org/Q18-1023/) | 英文图书／电影剧本；摘要或全故事问答；答案可为自由表达 | 原论文生成答案用 BLEU-1、BLEU-4、METEOR、ROUGE-L；答案排序任务另用 MRR | 必须区别摘要输入和全故事输入。它在原论文、LongBench 和 HELMET 中采用的评分并不一样，同名数据不自动产生可比成绩 | 已读 PDF §3.4 |
| [QuALITY，NAACL 2022](https://aclanthology.org/2022.naacl-main.391/) | 平均约 5,000 tokens 的英文长文四选一；限时快速阅读与不限时验证形成 HARD 子集 | 全体及 HARD 子集的 accuracy | HARD 表示快速略读／搜索不容易答对，**不是文本无答案**。题目经过人类答题和质量检查；难度可以参考此流程 | 已读 PDF §2、§3.1、§4和结论；[作者仓库](https://github.com/nyu-mll/quality)提供版本说明 |
| [LongBench，ACL 2024](https://aclanthology.org/2024.acl-long.172/) | 中英文、21 个数据集、6 大类，包括问答、摘要、分类、合成任务和代码 | QA 多为 F1；DuReader 用 ROUGE-L；摘要 ROUGE-L；分类／合成任务用各自准确率类函数；代码 edit similarity | QA 子集和整个套件平均分应区分。它的 HotpotQA 子集仅使用答案 F1，不能称原始 Hotpot 联合评价。中英文的分词规则也要固定 | 已读 PDF Table 1、§4.1；[task表](https://raw.githubusercontent.com/THUDM/LongBench/main/LongBench/task.md)、[metrics.py](https://raw.githubusercontent.com/THUDM/LongBench/main/LongBench/metrics.py)、[eval.py](https://raw.githubusercontent.com/THUDM/LongBench/main/LongBench/eval.py) |
| [LongBench v2，ACL 2025](https://aclanthology.org/2025.acl-long.183/) | **全部英文**；503 道四选一；8k–2M **words**；单／多文档、对话、代码、结构化数据等 | Accuracy，并按难度、长度及任务报告；zero-shot 与 zero-shot + CoT 分设 | 针对深理解而不是只有检索；其最短上下文也与当前 8k-token 平台预算不同。正式发表于2025，预印本始于2024；不要混写年份或 words/tokens | 已读 PDF §3.3、§4.1、Table 2／3；[官方结果汇总](https://raw.githubusercontent.com/THUDM/LongBench/main/result.py) |
| [HELMET，ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/f5332c8273d02729730a9c24dec2135e-Abstract-Conference.html) | 七类长上下文任务；可控制长度，包含英文长文问答、摘要、RAG、引用生成等 | 按任务：SubEM、MC accuracy、ROUGE F1、模型裁判；NarrativeQA裁判评分为流畅性0/1×正确性0–3，再标准化；摘要裁判用原子要点 P/R/F1×流畅性 | 明确检索分和理解分不能互相替代。SubEM 只看正确答案是否出现，可能忽略输出中的矛盾；judge 必须固定版本、提示并检查人类一致性 | 已读 [PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/f5332c8273d02729730a9c24dec2135e-Paper-Conference.pdf) §2.1–2.2、Table 3 |
| [Text2DistBench / Beyond Facts，Findings ACL 2026](https://aclanthology.org/2026.findings-acl.520/) | 从评论集合理解边缘、条件和联合分布，而非只回答孤立事实 | 分布估计 `1−TVD`；最常见／第二常见类别 accuracy | 对“集合总体信息”的理解是新增方向。`TVD=0.5×Σ|预测概率−真实概率|`，需要可靠类别标注；这不是一般阅读题都适用的分数 | 已读 PDF §3.3、§5、§6.1、Table 3 |
| [RPC-Bench，ACL 2026](https://aclanthology.org/2026.acl-long.1277/) | 研究论文理解；自由问答及二分类 claim verification；文本和图像设置分开 | 自由答：ROUGE-L、BERTScore；judge 对简洁／正确／完整各评0–5，派生 F1-like 和 informativeness；claim verification accuracy | 开放表达可用逐要点rubric，但该研究论文／多模态任务不直接等价于新闻阅读。裁判派生F1不是词重合F1，需盲审和人类校准 | 已读 PDF §3.5、§4.4、附录B.6／B.7／B.15 |

另找到并只读了 [Certifying Reading Comprehension in Large Language Models，AISTATS 2026](https://proceedings.mlr.press/v300/chaudhary26a.html) 的官方摘要和元数据。它针对预先定义、可独立采样的知识图谱提示分布给出正确率概率界，提醒固定题集的泛化边界；**未阅读全文，不用它支持本项目 bootstrap 已获得“形式认证”的说法**。

## 三类可复现的主指标

建议平台同时输出三组数值，保留原实现和自定义扩展的区别；公开基准与近期自建题库分成两个实验表。

1. **选择题正确率：**主要用于主旨、结构、语义条件和多步推理。`accuracy=正确选项数/全部预定题数`；固定四选一、随机基线25%；保持难度、选项数与出题规则一致，检查选项长度、位置和题干泄漏线索。格式失败另报，端到端主成绩失败计0。
2. **短答案 EM + official token F1：**事实／短答保留两个指标，数值题使用固定 DROP 实现或预先声明的数值／单位严格评分；不能将本项目中文字符F1称为LongBench官方中文F1。公开题库必须调用该基准实际 scorer；自建题库的别名、容差、分词和无答案规则随版本冻结。自由答案评分困难时不靠随意扩大别名解决。
3. **证据 EM / F1 + 答案证据联合分：**有明确证据金标的题报告 answer、support 和 joint。公开HotpotQA复现用原句级集合和官方公式；自建题库允许多个合法最小支持集合，并标明段落粒度。严格联合成功率用于检查“答对且有完整依据”，证据F1解释部分覆盖。按文章／语言宏平均是项目的附加统计，不替换公开原始聚合。

开放答案的逐要点rubric和人工盲审／固定judge作为扩展，分别报正确性、完整性、矛盾／无依据断言；未完成裁判与人工校准前不将裁判平均分混入主榜。Brier、拒答率、运行覆盖率和时间继续单独报告，不用速度抵消阅读错误。

Text2DistBench 与 RPC-Bench 的本次阅读材料提供英文题目／提示示例；这里未核实其具备中英文均衡评估。不能将这两项2026研究推广为已经验证本项目中文评分有效。

### HotpotQA 联合分必须使用正确公式

官方实现：答案精确／召回为 `Pa、Ra`，支持事实集合精确／召回为 `Ps、Rs`：

```text
Joint EM = Answer EM × Support EM
Joint P  = Pa × Ps
Joint R  = Ra × Rs
Joint F1 = 2 × Joint P × Joint R / (Joint P + Joint R)
```

分母为0则联合F1为0。**Joint F1 一般不等于 Answer F1 × Support F1。** 项目的“严格答案判定×段落严格集合判定”只借鉴严格联合的思想，答案形式、粒度、替代证据及聚合均不同；应标为 `custom_paragraph_joint_success`。

### 官方实现核查中发现的差异

- LongBench 中文 `qa_f1_zh_score` 使用 jieba 分词、逐token规范化后计算bag-of-token F1；当前项目中文字符F1与它不同。LongBench `eval.py` 对多个参考答案逐题取最高分。
- DROP 论文§5描述数值敏感及多跨度对齐。所读 AllenAI `drop.py` 使用 `linear_sum_assignment` 求最优一对一对齐；数字门控函数在gold含数字时要求预测数字至少与之相交，并不是任意额外数字／单位错误均被严格拒绝。项目如要严格检查所有操作数、符号和单位，需要另行定义，不能称原版已保证。
- LongBench v2 主表为严格accuracy。作者另讨论无合法选项时补偿25%随机分的附加表；抓取的 `result.py` 默认 `compensated=False`。项目应保持失败计0并报告失败率，不随意把无效回答补成随机正确。
- NarrativeQA原始生成评分、LongBench的答案F1及HELMET的模型裁判是三种协议。报告必须写出具体协议，不能将三个分数横向相减。

## 学术基准与本项目题库的实验边界

**公开基准用于外部参照，不作为“低污染”证据。** RACE、SQuAD、HotpotQA、DROP等已长期公开，评测模型可能见过正文、题目、解释或训练版本；即使调用官方scorer，也不能自动认定它测到的是新文阅读。新近发表的基准同样可能包含旧小说、旧论文和旧Wikipedia正文，论文年份不等于输入内容首次公开年份。

**近期自建题库用于控制实验条件和观察新文本理解。** 至少中英文各50篇隐藏测试文章、各10篇开发文章；文章首发日期与固定模型版本的可验证最晚训练完成上界对照，复用历史材料和无法确证首发日期的文本单独分层。无上下文作答、支持段落移除、反事实实体／数值干预可诊断记忆及文本依赖，但任何单项都不能证明零污染。正常与干预条件使用预先固定的同类提示、同一输出预算和逐题配对统计。

**不要把 MMLU / MMLU-Pro 等广泛知识考试当作纯阅读理解成绩，也不要把单独 NIAH / RULER needle 检索成绩当成完整理解能力。** HELMET 与 LongBench v2 的原论文都区分容易检索任务和需要整合、推理的任务；它们可以作为检索能力诊断，但不能替代主旨、条件、数量推理和信息边界题。

**长度实验需要先修正预算。** 现有演示平台使用8,192上下文及更保守的输入字节校验；这不是8,192词，也不是所有候选全文都可以输入。近期新闻短／中篇测试可先运行；QuALITY、LongBench和LongBench v2长篇测试需核实每个模型实际tokenizer和完整提示token数，保留足够输出空间。不能静默截掉证据后将结果写成“全文阅读成绩”。若使用公共长度子集或截取，必须标为子集／截取设置，不能声称复现完整公开榜。

## 必须补齐的验证

- 题目、答案、替代证据集合完成独立审核；主旨／论证题的可客观判定性优先于题量。
- 题型与能力维度关联预注册，不将同一个F1公式当作六项能力的有效性证据。
- 冻结提示、选择题答案提取、scorer、tokenizer、模型权重、量化和运行参数。模型规模／公司比较控制版本和推理条件，无法严格同参数时称“约7–9B同级比较”。
- 按语言、能力和文章长度报告样本数；用文章簇而非题目独立假设计算不确定性。近期自建题库的文章宏平均／paired cluster bootstrap属于项目分析选择，未取得形式认证。
- judge 模型版本与提示可复核，模型身份盲化，抽样双人核准并记录一致性／仲裁；避免将“裁判看起来合理”等同于可靠金标。

方法局限补充来源：[F1 is Not Enough!，EMNLP 2020](https://aclanthology.org/2020.emnlp-main.575/)（已读§6.6／§7）研究答案与解释评价，指出标准F1并不足以衡量对人类用户有用的解释。它支持增加解释性验证的动机，不能用来断言所有F1在所有阅读任务上均无效。

## 来源留档

来源快照位于 `docs/research-sources/literature-20261013/`，`manifest.json`记录源URL、抓取时间、HTTP状态、文件字节数、SHA-256及阅读范围。PDF文本副本仅供本地检索；不将下载资料重新发布为项目原创内容。`main/master`代码链接可能变化，复现使用快照哈希或另固定Git提交。上表没有把仅搜索到的摘要当成已核实的评分实现。
