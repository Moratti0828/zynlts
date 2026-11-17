# 演示题库与来源记录

当前版本为 `data/corpus.json` 中的 `1.1.0`：8 篇真实来源节选、32 道题，中英文各 4 篇；事实提取、情境推理、数值理解、不可回答各 8 题。初版 `1.0.0` 的 6 篇文章与 24 道题完整保留，所有原有文章对象及哈希均未改变。原始网页通过真实 HTTP 请求下载，首次 6 篇保存在 `data/raw/20261010-initial/`，另增 2 篇近期材料保存在独立的 `data/raw/20261010-recent/`。每个来源各有 HTML 原始字节、规范化全文 TXT 和采集元数据 JSON，各目录的 `capture-manifest.json` 汇总成功及失败记录。8 个来源全部真实采集成功，未修改已有测评运行记录。

题目由 AI 编制，并在本次开发中逐题对照所下载的来源核对。`reviewed: true` 仅表示经过这次编辑与证据校验，**不表示已经由用户、教师或独立评审者完成双人审题**。每道 `review_note` 均明确保留“AI编制并据来源核对；待用户/伙伴独立人工复核”。正式报告引用跑分前，应由你和结对伙伴独立复核题面、答案、证据和拒答标签。

## 实际来源和日期

| ID | 来源正文 | 来源网页发布日 `published_at` | 正文另载日期 | 评估范围 |
| --- | --- | --- | --- | --- |
| zh-housing-2025 | [住房租赁条例，国家林业和草原局官方转载](https://www.forestry.gov.cn/c/www/szxx/635119.jhtml) | 2025-07-21 | 国务院令公布日期 2025-07-16 | 公布说明及第二、七、八、十五条 |
| zh-data-sharing-2025 | [政务数据共享条例，生态环境部官方转载](https://www.mee.gov.cn/zcwj/gwywj/202506/t20250604_1120657.shtml) | 2025-06-04 | 国务院令公布日期 2025-05-28 | 公布说明及第三、十四、十七、十九条第一段 |
| zh-public-video-2025 | [公共安全视频图像信息系统管理条例，生态环境部官方转载](https://www.mee.gov.cn/zcwj/gwywj/202502/t20250211_1102044.shtml) | 2025-02-11 | 国务院令公布日期 2025-01-13 | 公布说明及第十三、十四、十七条 |
| en-bennu-2025 | [NASA’s Asteroid Bennu Sample Reveals Mix of Life’s Ingredients](https://www.nasa.gov/news-release/nasas-asteroid-bennu-sample-reveals-mix-of-lifes-ingredients/) | 2025-01-29 | 正文描述此前样本返回及本次新分析 | 4 个 NASA 解释段落 |
| en-nisar-2025 | [NASA-ISRO Satellite Lifts Off to Track Earth’s Changing Surfaces](https://www.nasa.gov/news-release/nasa-isro-satellite-lifts-off-to-track-earths-changing-surfaces/) | 2025-07-30 | 网页注明当天修正印度标准时发射时间 | 4 个 NASA 解释段落 |
| en-comet-2026 | [NASA’s SPHEREx Mission Tracks Brightening of Interstellar Comet](https://science.nasa.gov/blogs/3iatlas/2026/02/04/nasas-spherex-mission-tracks-brightening-of-interstellar-comet/) | 2026-02-04 | 页脚更新日期 2026-02-11；观测为 2025 年 12 月 | 4 个 NASA 解释段落 |
| zh-market-supervision-2026 | [市场监督管理所条例，生态环境部官方转载](https://www.mee.gov.cn/zcwj/gwywj/202609/t20260911_1165970.shtml) | 2026-09-11 | 国务院令公布日期 2026-09-06；计划施行日期 2026-11-01 | 公布说明及第三、五、十九条 |
| en-brown-dwarfs-2026 | [NASA’s SPHEREx Telescope Sees Menagerie of Brown Dwarfs](https://www.nasa.gov/missions/spherex/nasas-spherex-telescope-sees-menagerie-of-brown-dwarfs/) | 2026-10-08 | 文章标题下的发布日期；更新日期也为 2026-10-08 | 4 个 NASA/JPL 解释文字块 |

网页发布日期、法规公布日期、法规施行日期、事件发生日期、网页更新日期分别记录，不能互相代替。中文正文的 `promulgated_at` 存储更早的公布日期；`published_at` 保持来源网页实际显示的发布日。评估截止日期为用户本地日期 2026-10-10，八篇均在此之前。模型时间门槛由平台的模型元数据另行判定。

本次追加检索以 2026-08-01 至 2026-10-10 为近期窗口。NASA 2026-10-08 材料的标题区域明确显示发布时间，搜索到的 [JPL 原始发布页](https://www.jpl.nasa.gov/news/nasas-spherex-telescope-sees-menagerie-of-brown-dwarfs/)也显示 Oct. 8, 2026，未使用仅有更新日期的旧文充数。中文新材料 2026-09-11 转载发布，其所载法规本身在 2026-09-06 公布，同样位于近期窗口。由于计划 2026-11-01 才施行，题库保留 `effective_at`，相关推理题明示以 2026-10-10 判断，正确结论为尚未施行；材料存在不等于条例已经生效。其他检索命中包括 2026 年 7 月修订、8 月转载的集成电路法规，以及 2021 年法规的 2026 年转载页，未把这些转载日期当作最早公开日期使用。

仅凭“转载网页晚于模型发布”无法证明全文或事实从未在训练集中出现。法规可能先在别处公开；NASA 文章也包含 OSIRIS-REx 名称、雷达原理等旧事实。本题库的时间筛选降低直接文章泄漏风险，**不构成无污染保证**。报告须保留模型精确版本／digest、模型来源与已知训练信息，做“提供文章”和“不提供文章”的配对测试，并对能在闭卷中答出的题单独说明。检索、联网、外部知识库应在统一实验配置下关闭。

## 文本与使用范围

`scope` 全部为 `excerpt`。文章 `text` 只含所列原文段落，段间删节显式标为 `〔……〕` 或 `[…]`；没有改写原句或把概括伪装为原文。网页导航、推荐新闻、媒体联系方式、图片、图注、第三方直接引语和 NASA 标识均未纳入评估正文。`excerpt_line_ranges` 指向同名 TXT 的 1 起始行号，便于回查；每段原文可以逐行复核。

中文材料采用法规正文，[《中华人民共和国著作权法》第五条第一项](https://www.ncac.gov.cn/xxfb/flfg/flfg_532/202103/t20210309_50530.html)对法律、法规等具有立法、行政或司法性质的文件作出不适用规定；这个依据不扩展到政府网站所有新闻、摄影或页面设计。英文材料采用 NASA 署名解释性文字，[NASA Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)允许符合准则的教育、信息及事实性用途，并要求说明来源；NASA 网站上的第三方材料仍须另核权利。本题库已给出每篇来源与用途说明，未把普通新闻网站或机构转载统一视为公有领域。相关权利说明网页也已真实下载到 `data/raw/20261010-license/`，作为本次选择依据的快照。

初版每篇正文为 1265–1835 个 UTF-8 字节，低于平台当前每篇 6000 字节门槛。这是用于现场演示的小型短篇题库，题材主要是法规与太空科研，不能据此推断模型在长篇文学、跨篇整合或所有领域中的阅读能力。

## 校验记录与字段含义

- `article.sha256` 是 **实际送给模型的 `text` 的 UTF-8 字节** SHA256，包含删节标记与换行。
- `article.raw_sha256` 与同名元数据中的 `raw_sha256` 是原始 HTML 下载字节 SHA256；两者不可混用。
- `downloaded_at` 是实际采集时刻的 UTC ISO8601 时间。文章发布时间从来源文本核实，不使用下载时间充当发布时间。
- `raw_path` 相对项目根目录，指向不可覆盖的 HTML 快照；同名 TXT 与 JSON 保存提取内容和请求元数据。
- 24 道可回答题的所有 `evidence` 均是评估 `text` 中连续存在的原文字符串；数值题另在 `review_note` 说明计算或提取，单位以 `unit` 保存。
- 8 道不可回答题统一使用 `answers: ["无法从文章确定"]` 和空证据数组。英语题也显式要求这一固定拒答串，避免不同语言拒答写法影响演示评分。
- 初次验证核对了 6 个 HTML 哈希、6 个评估文本哈希、24 个唯一题号；追加版本再次验证所有 8 个来源、32 个题号、均衡题型、非空参考答案、原文证据和 6000 字节门槛，并验证原有六篇文章对象完全未变。该记录不是模型测评分数；旧版本跑分只对应旧版本题目，不能改写为已测试新增八题。

短答案题要求简短输出，降低措辞差异对 EM 的影响；`answers` 收录了少量明确同义或拼写变体。文本 F1、规则评分仍可能误判含义正确但措辞不同的回答，独立人工复核是必要的评估步骤。

## 重抓与扩充

在项目根目录运行：

```powershell
python scripts/collect_articles.py
python scripts/collect_articles.py --id en-comet-2026
```

脚本仅依赖 Python 标准库，默认向 `data/candidates/<UTC时间戳>/` 写入新的、`reviewed: false` 的候选快照。它不覆盖 `data/corpus.json`，不自动生成题目，不把新网页自动加入审核集。若指定 `--output`，必须使用新的或空的快照子目录；旧快照非空时脚本拒绝覆盖。抓取失败记录在候选 manifest，脚本返回非零退出码。

扩充时先核对来源权利及最早公开日期，再选取完整段落、编写四类问题、由结对伙伴独立复核，最后补齐哈希、来源与审题记录。转载来源发现更早版本时，应把较早日期和证据补入元数据，并重新检查模型时间门槛。用于调试的题目与最终报告的留出题库应分开冻结，避免根据最终题库反复改提示词导致评估过拟合。
