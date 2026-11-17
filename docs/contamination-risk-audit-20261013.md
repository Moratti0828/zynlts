# 现有文章与模型的训练污染风险审计

审计日期：2026-10-13（用户时区 Asia/Shanghai）。本报告完成了五个候选池 **402 篇**正文的本地自动追溯和风险筛查，以及 **20 篇、每个机构组两篇**的定向联网抽样；另外检查了已演示的 8 篇 / 32 题和已部署两模型的来源记录。全部检查属于技术审计及 AI 辅助复核，**不是人工审定，也没有开展训练成员检测实验**。

**结论：2026 年新网页配合 2024 年固定原始模型，能够降低“完整新文章进入这些模型训练”的风险，但当前证据不足以称题库零污染。新稿常含旧事实、先前论文、新闻转述和月报模板；答对某题不能证明看懂文章，更不能单凭答对证明训练时见过。**

可复现结果：`output/contamination-risk-audit-20261013.json`；逐篇抽样证据：`docs/contamination-web-samples-20261013.json`。脚本 `scripts/audit_contamination_risk.py` 只读原始数据，写上述审计 JSON，不修改候选、原始快照、manifest、现有演示题库或平台。

## 1. 检查覆盖和实测数量

| 项目 | 结果 | 可以得出的结论 |
|---|---:|---|
| 候选正文 | 402；中文 168、英文 234 | 已有真实正文，不是只有标题/网址 |
| 五池技术追溯 | 402 / 402 通过，0 技术错误 | raw/text 哈希、段落、原日期证据和 manifest/meta 可对应 |
| 候选页日期窗口 | 2026-01-13—2026-10-11 | 402 页均晚于保守模型发布上界 2024-09-19 |
| 2026 下半年 / 上半年 | 323 / 79 | 半年内文章并非全部都是近期首次披露 |
| 站内自报首次发布 | 39，均 GOV.UK Content API | 是本站 first_published_at，不是全球最早披露 |
| 未明确站内首次发布 | 363 | publication_meta、WordPress date、顶部日期仅支持来源页日期 |
| 全球最早公开时间已排除全部更早版本 | 0 | 有更早版本证据的文章可以修正日期，但本次没有宣称排除所有更早版本 |
| 定向联网抽样 | 20 / 402（约 5.0%） | 每个机构组 2 篇；非随机抽样，不用于估计总体污染率 |
| 未逐篇联网追查更早版本 | 382 | 全部在 JSON 明确标记 not_individually_web_searched |
| 已知训练成员 / 独立人工审定 | 0 / 0 | 不将风险标记冒充确认污染或人工审核 |

旧 `output/candidate-pool-audit.json` 只覆盖前四池 373 篇；本次新增完整覆盖第五池 29 篇 USGS，合计 402。不能以旧 373 审计替代全部文章。五池 manifest 的输入 SHA-256 已存入 JSON，以便重跑辨认数据变化。

机构组数量：CAS 54、MCT 45、NBS 40、MEE 29、NASA 51、NIH 40、LOC 40、Census 30、GOV.UK 多部门 39、USGS 34。CAS 下属研究所和 MCT 地方转载未被计作完全独立来源；GOV.UK 是门户而不是一个单独研究机构，原 API 中的 departments/organisations 逐篇另存，最终来源配额还应按实际作者和部门核定。

## 2. 风险必须拆成三个层次

1. **文章级直接接触**：完整正文、译文或近似转载可能进入预训练或后训练。若原始权重在文章全部公开版本之前已固定，且部署的是同一谱系，就能减少这种风险。
2. **答案级旧知识**：文章很新，但所问的法律规则、人物生平、科普定义、统计口径和历史数字早已公开。不读当前文章也可能答对。这会混淆阅读与先验知识，但不等同完整文章训练污染。
3. **测评建设与后续暴露**：开发/测试跨用了同一文章、同一论文或同模板新闻；调参已看过测试题；金标进入待测 prompt；题目公开后更晚模型可能接触。冻结切分、版本和输入日志才能控制这一类风险。

仅用新闻页面日期，最多支持第一层的一部分。训练 cutoff、模型首次公开时间、权重修订时间、发布页日期、事件日期、论文预印本日期、期刊 online 日期和文章更新时间是不同字段，不能互换。

## 3. 已发现的具体实例

### 演示法律题含已公开的旧规则

2025《住房租赁条例》对应演示题询问备案部门及厨房能否单独出租居住。然而 [2010-12-01《商品房屋租赁管理办法》官方旧页](https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/201012/t20101201_776815.html)第 8 条已有厨房等空间不得出租供人员居住，第 14 条已有租赁地建设/房地产主管部门登记备案规定。

这给 `zh-housing-2025-fact` 和 `zh-housing-2025-inference` 提供了 2024 前公开的相关答案规则，说明这两题不能作为“只能读新文章才知道”的强证据。**没有证据断言 Qwen 或 Llama 的训练包含该旧页。** 旧规则的 30 日指合同备案，2025 numeric 题的 30 日指企业报送开业信息，不能把同一个数字误当成完整问题已经相同。

### 2026 新闻的研究结果可以早于新闻公开

- NASA 2026-10-08 SPHEREx 褐矮星新闻对应 [arXiv:2607.00543](https://arxiv.org/abs/2607.00543)，v1 为 **2026-07-01**，已包含同一作者和 37 个对象样本。若以后加入 2026 年较晚模型，应按论文的公开时间核查，不能只按 10 月新闻隔离。目前 2024 固定模型与这次 2026 结果有更清楚的时间间隔。
- CAS 2026-10-09 非局域超表面新闻对应 [Advanced Functional Materials DOI 10.1002/adfm.78719](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adfm.78719)，期刊自报首次发表 **2026-09-26**；[院所原稿](https://sinano.cas.cn/news/kyjz/202609/t20260929_8287493.html)为 2026-09-29。更早预印本仍未排除。
- NIH 2026-09-23 脑图谱新闻与 Nature 当日论文含 1,494 位供体和超过 630 万细胞核；[同图谱早期会议摘要](https://alz-journals.onlinelibrary.wiley.com/doi/10.1002/alz70855_097915)在 **2025-12-23**已发表。Nature 的 Received 2024-07-24 是投稿时间，不能称 2024 年公众已见；DOI 中 `025` 也不能代替实际首次公开日期。
- CAS 2026 三阴性乳腺癌新闻对应 [Nature Medicine 2026-08-12 论文](https://www.nature.com/articles/s41591-026-04564-7)。同一试验 NCT05227664 的 **30 例早期结果**曾在 ESMO 2024 披露，[公司 2024-09-18 公告及交叉转载](https://www.prnewswire.com/news-releases/akesos-ivonescimab-plus-chemo-in-first-line-triple-negative-breast-cancer-showed-promising-preliminary-efficacy-and-good-safety-at-esmo-2024-302248727.html)可查。早期 30 例不等于 2026 最终 36 例和 22.1 月随访，不能把所有最终题都标旧答案。9 月 18 日虽早于保守 9 月 19 日发布上界，却晚于已保存 Qwen 7B 的 9 月 16 日原 tensor 上传和 Llama 7 月 23 日发布，也不能据此推断当前模型见过该公告。

### 新文章仍会复用旧知识

- MCT 2026 暑期提示中的防暑、防雷、防雨、系安全带、穿救生衣及避开未开放区域等建议，在 [2024-06-27 官方提示](https://www.mct.gov.cn/whzx/whyw/202406/t20240627_953746.htm)已有重叠内容。
- LOC 2026 Geraldine Brooks 人物稿包含 *March* 获 2006 年普利策奖；[官方获奖名单](https://www.pulitzer.org/prize-winners-by-year/2006)明确记录旧事实。LOC 2026 Kate McKinnon 稿提到的书名和人物设定在 [2024-02-13 公告](https://www.kirkusreviews.com/news-and-features/articles/kate-mckinnon-to-write-middle-grade-fiction-series/)与 2024-07-11 书评已有披露，不能以书的 2024-10-01 正式发行时间认定之前无人知道。
- NIH 2026 HIV 药物/MS 小鼠研究的背景“NRTI 能抑制炎症小体”，有 [2014 Science 原论文](https://pubmed.ncbi.nlm.nih.gov/25414314/)支持；这不同于 2026 特定模型中恢复视力/运动的最新结果。
- USGS 2026 狩猎和钓鱼日科普引用 2019 鸟类数量下降研究，还介绍 1966 调查与 1995 管理框架。新事件稿中的背景和被测答案应分开核查。

### 误命中旧数字不等于找到同一道答案

2026 国庆新闻和 2023 双节报告均出现 8.26 亿人次，但时期、假期长度和收入数字不同。单个数字重复不能证明 2026 完整事件结果此前公开；这种例子说明答案风险筛查必须保留主体、时间、指标和范围。

## 4. USGS 日期误取和同源泄漏检查

原采集中两个 USGS 页误取了推荐区日期，已有 `publication-date-processing-log.json` 记录，本次读取原 HTML 重新核对：

- `en-usgs-654e58f9c0cc` 狩猎和钓鱼日稿：2026-06-30 → **2026-09-24**；顶部作者/日期相符。
- `en-usgs-8b7e767b230c` Hurricane Readiness：2026-10-09 → **2026-06-02**；修改记录已留存。

本次没有改原始候选或日期。这类选择器问题即使修好了，也只解决来源页时间，不证明全球首发。

402 篇无相同正文哈希组、无重复 URL，但词面高相似筛查命中 **4 对、5 篇，形成 2 个明显家族**：NBS 7/8/9 月采购经理指数三稿；USGS 新墨西哥低空扫描公告与恢复扫描公告。相似度规则为同语言五单位 shingle Jaccard ≥ 0.65 或短文覆盖 ≥ 0.85，并约束长短比；它会漏掉改写、翻译与同一论文不同新闻，不能当语义去重完成证明。

另外，已演示 `en-brown-dwarfs-2026` 和候选 `en-nasa-5a9a11764321` 是**同一来源新闻**，只是全文/节选不同；即使正文哈希不同也必须同簇。MEE 的主稿和一周要闻也可能重复事件。开发与测试要按文章/论文/事件家族切分，不能只按 URL 随机分。

## 5. 模型证据与不能证明的事项

已部署 Qwen2.5 7B 与 Llama3.1 8B 的官方 Ollama manifest、模型层 digest、原模型卡及 Qwen 原 tensor 历史存于 `docs/model-source-snapshots/`。Llama 模型卡将 **2023-12**描述为预训练数据截止，**2024-07-23**为模型发布；前者不能自动覆盖全部指令微调/偏好训练。

Qwen 已存原 tensor 首次上传 revision 为 `d1e200fcf95ef0d4326873ddf63e5562d5f1fdbb`（2024-09-16），当前四个原 tensor 的 LFS SHA 与当时一致。可据此追踪这些原权重，但上传时间仍不是逐条训练语料的 cutoff。

**digest 只固定本次运行的模型字节，不能独自证明原 checkpoint → Ollama GGUF 的完整转换谱系，也不能说明全部训练数据。** 原卡版本、权重版本、模板和量化参数应分开保存。对后续六模型计划，`model-comparison-metadata-20261013.json`记录官方原 tensor 历史路径/大小/SHA 与当前是否一致，未下载并认证运行时权重映射，需在部署阶段继续验证。

若新加入模型的固定权重发布时间晚于当前文章/其论文公开时间，该模型不能直接进入同一个“时间隔离已满足”的主比较。应补更晚文章、核更早底层披露，并重新冻结全部模型共同合格的子集；或者另设“近期模型现实表现”组，明确污染证据较弱。

## 6. 对正式题库的处理规则

1. 保留 2024 年原始模型作为本轮时间隔离主组；不在这些模型上训练或微调测评文章与金标。
2. 选定 120 篇后逐篇追查院所原文、预印本、期刊 online、报告/数据释放和既往转载，保存 earliest_observed_publication 与证据 URL；没有找全时标 unknown，不能写全球首发已证明。
3. **逐题**记录答案是否是旧背景、本文首次给定的新细节、必须组合文本才能得到的结论或未知。旧背景题可作阅读释义题，但不宣传为只能从新文章获知；避免让这类题支配成绩。
4. 法规、科普定义、名人生平、单个数字题优先加限定条件、跨段组合与证据要求；正确答案+完整证据的联合评分只检查输出支持，不能证明内部推理来源。
5. 同论文、事件、统计月报模板和译文归同源簇，再做 20 开发 / 100 隐藏测试。已展示 8 篇 / 32 题留开发；不得再次包装为隐藏独立测试。未曝光且未跨簇的题才进入正式集。
6. 冻结文章哈希、题目、评分规则和模型原始 revision；保存 prompt，确认金标、题库文件路径、搜索工具和浏览器结果未提供给待测模型。
7. 另外开展问题单独给模型的先验知识探针：答对仅标“可以在无当前正文情况下作答”，不直接判已训练。该提示与阅读任务不同，不能把两个分数差当成因果阅读增益或直接相减作主成绩。
8. 增设少量人工构造的成对反事实素材，明确标 synthetic，修改数字/实体/规则并同步改金标，检查输出是否跟随所给文字。原稿和改稿同簇，不改原始真实文章，不把合成素材充当 120 篇真实来源。

风险不应被压成无依据的“低/中/高污染率”。本轮可报告“来源时间晚于原模型，但全球最早时间/答案旧知识/运行时谱系仍有待核查”，并分别给出上述覆盖率与证据。

## 7. 学术界的检测和缓解依据

| 论文 | 对本项目的具体作用 | 使用限制 |
|---|---|---|
| [Shi et al., Detecting Pretraining Data from Large Language Models, ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/e32ad85fa27be4a9868d55703f01323e-Abstract-Conference.html) | Min-K% Prob 利用低概率 token 的似然作训练成员推断信号 | 需要 token-level likelihood 和匹配的校准样本；当前 Ollama JSON 生成日志不足以直接运行；数值不等同训练成员证明 |
| [Fu et al., Does Data Contamination Detection Work (Well) for LLMs?, Findings NAACL 2025](https://aclanthology.org/2025.findings-naacl.291/) | 复查成员推断的假设与分布偏移问题 | 其部分案例接近随机，不应把检测未命中当无污染认证 |
| [White et al., LiveBench: A Challenging, Contamination-Limited LLM Benchmark, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/e4a46394ba5378b3f9a186a5b4c650d1-Abstract-Conference.html) | 使用持续更新的新来源与可客观评分题，减少固定基准反复曝光 | 引用会议正式题名 Contamination-Limited，避免把早期预印本的 Contamination-Free 标题当零风险保证 |
| [Chen et al., Benchmarking Large Language Models Under Data Contamination: A Survey from Static to Dynamic Evaluation, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.511/) | 支持把污染检测与缓解分开，并采用新来源/动态题目 | 新样本、动态改写和黑盒识别各有局限，不能推断未知完整训练集 |

## 8. 每机构组两篇联网抽样索引

下表的“早于 2024-09-19”针对**匹配范围内观察到的公开证据**，不是待测模型训练摄入标签。unknown 表示未确定/未查到，不表示没有更早版本。CAS 早期试验数据不代表全部最终数据；USGS 历史事件不等同早期网页存档。详细匹配范围、检索词、URL、访问失败和限制见配套 JSON。

| 机构组 | 候选文章（原文） | 找到的较早证据 | 早于2024-09-19 |
|---|---|---|---|
| CAS | [非局域超表面实现激子发射定向调控](https://www.cas.cn/syky/202609/t20260930_5121254.shtml) | [2026-09-26](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adfm.78719) | 否，所找到版本仍较晚 |
| CAS | [晚期三阴性乳腺癌一线治疗取得重要进展](https://www.cas.cn/syky/202608/t20260819_5118620.shtml) | [2024-09-18](https://www.akesobio.com/en/media/akeso-news/240918-1/) | 是，仅匹配范围 |
| NBS | [2026年1—8月份社会消费品零售总额增长1.1%](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965311.html) | 未确定更早版本 | unknown |
| NBS | [2026年7月份规模以上工业增加值增长4.5%](https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965055.html) | 未确定更早版本 | unknown |
| MCT | [2026年国庆节假期国内出游8.26亿人次](https://www.mct.gov.cn/whzx/whyw/202610/t20261009_967315.htm) | 未确定更早版本 | unknown |
| MCT | [文化和旅游部端午节假期和汛期、暑期出游提示](https://www.mct.gov.cn/whzx/whyw/202606/t20260605_966153.htm) | [2024-06-27](https://www.mct.gov.cn/whzx/whyw/202406/t20240627_953746.htm) | 是，仅匹配范围 |
| MEE | [生态环境部党组书记孙金龙赴吉林省调研生态环境保护工作](https://www.mee.gov.cn/ywdt/hjywnews/202609/t20260923_1174311.shtml) | 未确定更早版本 | unknown |
| MEE | [中国环境与发展国际合作委员会2026年年会在京开幕](https://www.mee.gov.cn/ywdt/hjywnews/202609/t20260928_1174960.shtml) | 未确定更早版本 | unknown |
| NASA | [NASA’s SPHEREx Telescope Sees Menagerie of Brown Dwarfs](https://www.nasa.gov/missions/spherex/nasas-spherex-telescope-sees-menagerie-of-brown-dwarfs/) | [2026-07-01](https://arxiv.org/abs/2607.00543) | 否，所找到版本仍较晚 |
| NASA | [NASA Model Wing Lights Up During First Pressure Sensitive Paint Tests](https://www.nasa.gov/centers-and-facilities/langley/nasa-model-wing-lights-up-during-first-pressure-sensitive-paint-tests/) | 未确定更早版本 | unknown |
| NIH | [Modified HIV drug reverses vision loss and paralysis in multiple sclerosis model](https://www.nih.gov/news-events/news-releases/modified-hiv-drug-reverses-vision-loss-paralysis-multiple-sclerosis-model) | [2014-11-21](https://pubmed.ncbi.nlm.nih.gov/25414314/) | 是，仅匹配范围 |
| NIH | [Scientists develop high-resolution molecular maps of Alzheimer’s and related brain disorders](https://www.nih.gov/news-events/news-releases/scientists-develop-high-resolution-molecular-maps-alzheimers-related-brain-disorders) | [2025-12-23](https://alz-journals.onlinelibrary.wiley.com/doi/10.1002/alz70855_097915) | 否，所找到版本仍较晚 |
| LOC | [Geraldine Brooks – on life, love and loss – at the Library | Timeless](https://blogs.loc.gov/loc/2026/06/geraldine-brooks/) | [2006](https://www.pulitzer.org/prize-winners-by-year/2006) | 是，仅匹配范围 |
| LOC | [A “High Octane” Kate McKinnon at the National Book Festival | Timeless](https://blogs.loc.gov/loc/2026/09/a-high-octane-kate-mckinnon-at-the-national-book-festival/) | [2024-02-13](https://www.kirkusreviews.com/news-and-features/articles/kate-mckinnon-to-write-middle-grade-fiction-series/) | 是，仅匹配范围 |
| Census | [Poverty Rate for the Hispanic Population Fell to 13.9%, Lowest on Record](https://www.census.gov/library/stories/2026/09/hispanic-poverty.html) | 未确定更早版本 | unknown |
| Census | [Parental Financial Support Does Not End When Children Grow Up, Even After They Move Out](https://www.census.gov/library/stories/2026/09/parental-support-to-adult-children.html) | 未确定更早版本 | unknown |
| GOV.UK multiple departments | [Upfront help cuts placement costs for healthcare students](https://www.gov.uk/government/news/upfront-help-cuts-placement-costs-for-healthcare-students) | [2025-07-03](https://www.gov.uk/government/publications/10-year-health-plan-for-england-fit-for-the-future) | 否，所找到版本仍较晚 |
| GOV.UK multiple departments | [Government pledges earlier support to tackle mental health crises](https://www.gov.uk/government/news/government-pledges-earlier-support-to-tackle-mental-health-crises) | 未确定更早版本 | unknown |
| USGS | [America at 250, Seen from Space](https://www.usgs.gov/news/featured-story/america-250-seen-space) | [1976-07](https://www.usgs.gov/media/images/1976-portrait-usa) | unknown |
| USGS | [The USGS Celebrates National Hunting and Fishing Day, an Occasion with Deep Ties Across the Bureau’s Diverse Science](https://www.usgs.gov/news/featured-story/usgs-celebrates-national-hunting-and-fishing-day-occasion-deep-ties-across) | [2019-10-04](https://www.science.org/doi/10.1126/science.aaw1313) | 是，仅匹配范围 |

