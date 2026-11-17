# 新下载候选文章池独立审计

审计日期：2026-10-11。状态：`complete_download_snapshot_audit`。审计器只读取候选文件，不修改原始快照、采集器、现有 8 篇演示题库或评分器。

本报告是技术检查与 AI 辅助审查；**人工审定文章、已审金标题目和正式冻结文章均为 0**。正文可追溯不等于语义质量、授权、最早首发或完全无训练污染已经证明。

## 核实后的数量

manifest 中候选记录 373；独立 URL 373；不同正文 SHA-256 373。技术完整性通过 373，拒收/待修复 0；manifest/metadata 关键字段不一致 0 条。

| 语言 | 下载候选 | 技术完整性通过 | 同时达建议长度 | 当前 6000 字节模型正文预算内 | 长度中位数 |
|---|---:|---:|---:|---:|---:|
| zh | 168 | 168 | 108 | 135 | 689 |
| en | 205 | 205 | 201 | 157 | 719 |

建议长度是中文至少 600 个汉字、英文至少 300 个正则分词，不是采集硬门槛或自动入选标准；短而完整的文章仍可人工例外，长文章也不能擅自截断。正文预算仅指当前 6000 UTF-8 字节约束，提示词和输出还占额外预算。

## 真实性、日期与完整性

逐篇核对 metadata.text 的 SHA-256、txt 保存字节、原始快照 SHA-256、段落拼接一致性、来源地址、语言标签、日期字段和未审状态，并核对每段文字能在机构正文选择器/API body 中找到。txt 的 Windows CRLF 转换及单个末尾换行与正文哈希分开报告，不删除正文空白。NASA API item 重序列化文件不是整个 HTTP 响应，须连到 discovery 原始响应后才构成完整取证链。

来源明确自报 first_published_at 的 39 篇，未自报的 334 篇；全球最早公开时间独立核定为 0 篇。publication_meta、页面 header 或 WordPress date 只能支持该来源的发布日期；不自动证明没有更早论文、转载或早期报道。URL 日期、Last-Modified、updated 字段没有被当作首发证据。

## 重复与正文污染风险

准确重复正文组 0；重复 URL 组 0；高相似文本对 3。五单位 shingle 筛查不能代替语义独立性审查：同一统计系列、同一事件的报道以及共享调查说明应归入同组，划分开发/测试时不得跨组。

- `below_recommended_length`：64 篇。
- `earliest_publication_unverified`：334 篇。
- `exceeds_current_6000_byte_passage_budget`：81 篇。
- `language_label_requires_review`：2 篇。
- `standalone_repeated_title_or_caption`：8 篇。

## 来源、领域与体裁

来源计数按采集 provider，而不是已经人工核定的作者或独立机构。GOV.UK 的原始 Content API 中 organisations 在 JSON 审计记录中另列；科学院下属研究所也不能自动当成完全独立文章来源。领域与体裁目前仅是 provisional 标签。

| 来源 | 候选数 |
|---|---:|
| cas | 38 |
| cas_health | 16 |
| census | 30 |
| govuk | 39 |
| loc | 40 |
| mct | 23 |
| mct_local | 22 |
| mee | 29 |
| nasa | 51 |
| nbs | 40 |
| nih | 40 |
| usgs | 5 |

领域：`{"public_policy": 39, "history_culture": 85, "science_technology": 89, "health_life": 56, "environment": 34, "economy_society": 70}`。

体裁：`{"public_information": 39, "cultural_narrative": 62, "science_explanation": 56, "research_explanation": 94, "cultural_news": 23, "environmental_news": 25, "weekly_digest": 4, "statistical_report": 40, "statistical_explanation": 30}`。

## 每机构正文抽样

下列每机构至少两篇（若总共不足两篇则全看）按最短与中位长度抽样，结合 raw 正文与头尾文本作独立 AI 辅助核对。全部篇目已执行技术追溯，但本抽样不属于人工审稿或对各句事实的核验。

- `zh-cas-1cf079b15eb7` [非局域超表面实现激子发射定向调控](https://www.cas.cn/syky/202609/t20260930_5121254.shtml)：1226 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-cas-ff55790ecfac` [二维滑移铁电体研究取得进展](https://www.cas.cn/syky/202609/t20260930_5121282.shtml)：2129 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `zh-cas_health-56f6d8cf3bdc` [科研人员提出轻石脑油全组分梯级膜分离新策略](https://www.cas.cn/syky/202609/t20260902_5119531.shtml)：1713 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-cas_health-368f15751647` [食品废弃物转化为单细胞蛋白和油脂技术研究获进展](https://www.cas.cn/syky/202608/t20260828_5119250.shtml)：2120 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-census-3256da0de89d` [Sales of Lottery Tickets Nearly Doubled and Prizes More Than Doubled From 2008 to 2024 ](https://www.census.gov/library/stories/2026/04/state-lottery-ticket-sales-soar.html)：2413 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-census-50c203150ac7` [Census Bureau Data Highlight Continued Importance of Nation&#8217;s Storied Manufacturing Industry](https://www.census.gov/library/stories/2026/09/manufacturing-week.html)：5418 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-govuk-91f2b3d6c317` [Pathway to stronger public control of the water industry revealed](https://www.gov.uk/government/news/pathway-to-stronger-public-control-of-the-water-industry-revealed)：2328 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`无`。
- `en-govuk-b8e1e97a1bce` [Chancellor announces Bank of England appointments](https://www.gov.uk/government/news/chancellor-announces-bank-of-england-appointments--2)：5022 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`无`。
- `en-loc-a481baded3c6` [Ralph Ellison’s “Invisible Man” | Timeless](https://blogs.loc.gov/loc/2026/05/ralph-ellisons-invisible-man/)：1946 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-loc-7c6b39a54e5e` [“By the Dawn’s Early Light…” | Timeless](https://blogs.loc.gov/loc/2026/07/by-the-dawns-early-light/)：4339 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `zh-mct-931a35733be0` [2026年中国图书馆年会在四川成都举办](https://www.mct.gov.cn/whzx/whyw/202609/t20260914_967140.htm)：1270 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-mct-e0316dd02e09` [文化和旅游部印发《文化和旅游发展“十五五”规划》](https://www.mct.gov.cn/whzx/whyw/202609/t20260916_967163.htm)：1949 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-mct_local-2acb43c6a355` [云南座谈研究科技赋能文旅发展](https://www.mct.gov.cn/whzx/qgwhxxlb/yn/202609/t20260903_967050.htm)：1231 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-mct_local-f5f1a9d30f0c` [浙江打造“泛舟浙里”交旅融合品牌](https://www.mct.gov.cn/whzx/qgwhxxlb/zj/202608/t20260807_966804.htm)：1657 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-mee-8eceb1dab4e4` [生态环境部召开部常务会议](https://www.mee.gov.cn/ywdt/hjywnews/202609/t20260903_1165072.shtml)：1649 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `zh-mee-d776ca30e3df` [生态环境部部长黄润秋视频出席第十二次金砖国家环境部长会议](https://www.mee.gov.cn/ywdt/hjywnews/202608/t20260820_1164285.shtml)：2321 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-nasa-3724daf1d350` [NASA Hosts Virtual Artemis Webinar for Blind, Low-Vision Community](https://www.nasa.gov/general/nasa-hosts-virtual-artemis-webinar-for-blind-low-vision-community/)：1601 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `en-nasa-6b6f9a8e2d18` [NASA Celebrates Restoration of Guam Station Damaged by Typhoon Mawar ](https://www.nasa.gov/technology/space-comms/nasa-celebrates-restoration-of-guam-station-damaged-by-typhoon-mawar/)：4245 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `zh-nbs-4517b57fcb4b` [2026年7月份能源生产情况](https://www.stats.gov.cn/sj/zxfb/202608/t20260817_1965051.html)：2393 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `zh-nbs-0f91e321dc8c` [2026年9月上旬流通领域重要生产资料市场价格变动情况](https://www.stats.gov.cn/sj/zxfb/202609/t20260914_1965293.html)：7937 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, exceeds_current_6000_byte_passage_budget, standalone_repeated_title_or_caption`。
- `en-nih-1191eb614c92` [NIH launches new office to advance human-based research and reduce animal use](https://www.nih.gov/news-events/news-releases/nih-launches-new-office-advance-human-based-research-reduce-animal-use)：2791 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-nih-15d882160d60` [Neuroprosthesis for paralysis enables simultaneous speech and body language](https://www.nih.gov/news-events/news-releases/neuroprosthesis-paralysis-enables-simultaneous-speech-body-language)：4864 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。
- `en-usgs-83facc5ef8bb` [The Loneliest Seismometers on Earth](https://www.usgs.gov/news/science-snippet/loneliest-seismometers-earth)：1673 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified, below_recommended_length`。
- `en-usgs-fe34467182ef` [From Earth to Sky: How Minerals Create the Dazzling Colors of Independence Day Fireworks](https://www.usgs.gov/news/featured-story/earth-sky-how-minerals-create-dazzling-colors-independence-day-fireworks)：4562 字节；日期原值在 raw 中：True；未追溯段落：[]；标记：`earliest_publication_unverified`。

## 入选前仍需完成

1. 清理导航、相关链接、标题重复与无图可读的图注，保存清理前后版本及可追溯段落映射。
2. 核查转载、论文与事件的最早公开时间、授权和同源内容组；处理高相似统计模板家族。
3. 依中文 60 / 英文 60 的目标按领域、体裁、长度选 120 篇，开发 20 / 正式 100；两语言分别报告。候选数量不能保证这些配额已经满足。
4. 编写真正覆盖理解操作的问题及完整证据链，独立复核后冻结；当前候选不含正式参考答案，不能直接用于排名。
