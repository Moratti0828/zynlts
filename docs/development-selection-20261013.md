# 20篇开发集候选选择与采编清单

更新日期：2026-10-13（北京时间）。状态：`selected_provisional / candidate / ai_checked`；真实人工审核0，冻结0。

**已选中文10篇、英文10篇；均为2026年下半年页面。AI读取20篇真实正文并核对正文/原始文件哈希。已有两篇16题AI草稿，本次新增可执行题0，新增60条采编方向；160题只是目标。**

机器清单：[development-selection-20261013.json](../data/annotation/development-selection-20261013.json)。这不是金标或正式测试集，不改已有16题。

## 来源、领域和长度

|领域|中文|英文|
|---|---:|---:|
|科学技术|2|2|
|环境与能源|1|1|
|公共政策|1|1|
|社会与文化|2|2|
|健康与生命科学|2|2|
|经济与产业|2|2|

全体10个发布机构组，最多CAS4/20=20%；中文CAS4/10=40%，不可忽略来源集中。CAS健康、MCT地方栏目不另算机构。中文为CAS/NBS/MCT/MEE，英文为NASA/Census/NIH/LoC/USGS/GOV.UK。

|范围|中文短/中/相对长/超目标|英文短/中/相对长/超目标|
|---|---|---|
|下载全文|2/3/4/1|1/6/2/1|
|拟呈现（未冻结）|2/4/4/0|1/6/3/0|

中文用汉字300—600、601—1200、1201—2000；英文用词数（含数字）200—400、401—800、801—1400。不是模型token。完整旅游案例超目标，拟完整选前8案；LoC作者前言可完整移至署名区。全文始终保存，选段另存后冻结，无静默截断。

正文有实验机制、统计、案例、策略和文化叙事，但机构新闻仍支配；正式100篇必须补独立评论、文学叙事等体裁。短文如不能提供独立8题应替换，不能硬编计算题。

## 新增更早版本发现与替换

NIH候选`en-nih-3d1dab450396`在2026-10-07发布肺类器官新闻，对应Nature论文`10.1038/s41586-026-11114-1`已有[2023-05-05预印本v1](https://doi.org/10.21203/rs.3.rs-2870695/v1)。[Crossref元数据](https://api.crossref.org/works/10.21203%2Frs.3.rs-2870695%2Fv1)明确`is-preprint-of`关系和日期，v1摘要已有完整肺组织ALI类器官、局部病毒特异适应性T细胞反应。2026新闻不能建立2024模型时间隔离，撤出本次优先选择，替换为Linked Discoveries工具首公开版报道。

Crossref证据字段与响应SHA保存在机器清单；ResearchSquare直读403、PMC浏览器验证，未完整比对v1与2026新增细节。只能确认更早同研究和已出现机制，不说全部新答案旧，更不说模型训练见过。旧402篇审计仅20篇联网抽查，该稿不在旧抽查样本内。

## 中文10篇

### ZH-01　2026年1—8月份社会消费品零售总额增长1.1%

- ID：`zh-nbs-02a36a9fc6f8`；领域：经济与产业；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965311.html)；页面日期2026-09-15；全文1334汉字数（longer），拟呈现1027（medium）。
- 时间、范围与缺口：现有devpilot节选，含统计口径；官网2026-09-15，统计定义旧，有限检索不是全球首发证明。
- 最早观察到的公开证据：2026-09-15，[证据来源](https://www.stats.gov.cn/sj/zxfb/202609/t20260915_1965311.html)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-nbs-02a36a9fc6f8.txt)；源簇建议`nbs-retail-monthly-series`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。
- 复用现有8道AI草稿，0人工。

可出题方向（不是冻结题/金标）：

- **D4** 用累计总额减除汽车额求汽车零售额。关系核对：327569−301764亿元，不能混单月；源TXT锚点：p001。
- **D3** 为什么新网上消费指标不能直接与旧指标比较。关系核对：服务平台范围扩大，总指标口径不可比；源TXT锚点：p060。
- **D6** 扣除价格后的实际增速是多少。关系核对：只有名义增速，必要信息缺失；源TXT锚点：p037。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-02　国家统计局关于2026年早稻产量数据的公告

- ID：`zh-nbs-d8dd3b95e0c6`；领域：经济与产业；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://www.stats.gov.cn/sj/zxfb/202608/t20260821_1965086.html)；页面日期2026-08-21；全文651汉字数（medium），拟呈现651（medium）。
- 时间、范围与缺口：官网和正文2026-08-21；更早表包待查。保留表格列单位，空白依注释为无早稻生产。
- 最早观察到的公开证据：2026-08-21，[证据来源](https://www.stats.gov.cn/sj/zxfb/202608/t20260821_1965086.html)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-nbs-d8dd3b95e0c6.txt)；源簇建议`nbs-early-rice-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** 比较湖南江西的面积与产量排序并求产量差。关系核对：740.4−688.6万吨；面积排序不等于产量排序；源TXT锚点：p022, p026。
- **D3** 面积略增为何总产量下降。关系核对：面积×单产，单产下降需一起读；源TXT锚点：p002, p048。
- **D6** 各省本期售粮均价是多少。关系核对：无价格，不能从产量推得；源TXT锚点：p006。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-03　研究揭示月壤水冰导热率双控新机制

- ID：`zh-cas-5dc9ec97bf04`；领域：科学技术；拟适用维度：D1, D2, D3, D5, D6。
- [来源正文](https://www.cas.cn/syky/202609/t20260918_5120585.shtml)；页面日期2026-09-22；全文1216汉字数（longer），拟呈现1216（longer）。
- 时间、范围与缺口：出版商索引2026-09-12，CAS页9月22日；直读出版商失败，日期待复核。完整论证，预印本仍待查。
- 最早观察到的公开证据：2026-09-12，[证据来源](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2026JE009900)（publisher_search_index;direct_open_failed；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-cas-5dc9ec97bf04.txt)；源簇建议`doi-10.1029-2026je009900`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D3** 相近含冰量为何两种样品导热率不同。关系核对：形态→冰桥/接触热阻→连续传输网络；源TXT锚点：p003, p004。
- **D2** 能否只测导热率唯一确定冰丰度。关系核对：含量与形态共同控制，不唯一；源TXT锚点：p006。
- **D5** 核磁和电镜各支持什么结论。关系核对：未冻水可忽略与孔隙冰连接分别验证；源TXT锚点：p002, p005。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-04　非局域超表面实现激子发射定向调控

- ID：`zh-cas-1cf079b15eb7`；领域：科学技术；拟适用维度：D1, D2, D3, D6。
- [来源正文](https://www.cas.cn/syky/202609/t20260930_5121254.shtml)；页面日期2026-10-09；全文368汉字数（short），拟呈现368（short）。
- 时间、范围与缺口：旧审计论文2026-09-26、研究所9月29日早于CAS页10月9日；均晚于模型，但更早版本未穷尽。完整短文，不从未提供图读数。
- 最早观察到的公开证据：2026-09-26，[证据来源](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adfm.78719)（existing_contamination_risk_audit_web_evidence；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-cas-1cf079b15eb7.txt)；源簇建议`doi-10.1002-adfm.78719`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D3** 对比传统局限与新共振说明方向控制。关系核对：集体光场有空间相干性与高品质因子；源TXT锚点：p001, p003。
- **D2** 偏转是否与手性无关。关系核对：文内明确手性依赖；源TXT锚点：p004。
- **D6** 精确偏转角和效率是多少。关系核对：正文没有量化数值；源TXT锚点：p004。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-05　长效神经融合脑机界面研究取得进展

- ID：`zh-cas_health-d9258d90ea32`；领域：健康与生命科学；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://www.cas.cn/syky/202608/t20260818_5118510.shtml)；页面日期2026-08-27；全文925汉字数（medium），拟呈现925（medium）。
- 时间、范围与缺口：出版商明确2026-08-04首发，研究所8月17日、CAS8月27日。交替肽抗污有2021背景；问新神经电极实验，动物不等于人体。
- 最早观察到的公开证据：2026-08-04，[证据来源](https://advanced.onlinelibrary.wiley.com/doi/10.1002/adma.74519)（publisher_page_First_published_read；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement/snapshots/zh-cas_health-d9258d90ea32.txt)；源簇建议`doi-10.1002-adma.74519`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** 约为裸电极组1/5对应减少比例。关系核对：约80%，保留约数；源TXT锚点：p004。
- **D3** 分子响应、长期记录与无损取出如何相连。关系核对：抑炎恢复功能与抗生物黏连分别支持不同结果；源TXT锚点：p003, p004, p005。
- **D6** 人体300天植入成功率是多少。关系核对：只有动物模型验证；源TXT锚点：p002。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-06　研究揭示甲基转移酶SET7调控抗病毒天然免疫分子机制

- ID：`zh-cas_health-31517790bbba`；领域：健康与生命科学；拟适用维度：D1, D2, D3, D5, D6。
- [来源正文](https://www.cas.cn/syky/202608/t20260827_5119137.shtml)；页面日期2026-09-10；全文690汉字数（medium），拟呈现690（medium）。
- 时间、范围与缺口：PubMed Article date和研究所正文支持2026-08-25在线，CAS9月10日；URL路径8月1日不是日期证据。SET7背景旧，IRF3第98位为本研究关系。
- 最早观察到的公开证据：2026-08-25，[证据来源](https://pubmed.ncbi.nlm.nih.gov/42640792/)（PubMed_index_and_institute_body；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement/snapshots/zh-cas_health-31517790bbba.txt)；源簇建议`doi-10.1073-pnas.2601297123`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D3** 建立SET7到抗病毒表达下降的必要链。关系核对：第98位单甲基化→磷酸化二聚化受抑→干扰素降低；源TXT锚点：p004。
- **D2** 比较SET7作用和敲除的方向。关系核对：抑制与敲除后增强不得颠倒；源TXT锚点：p003。
- **D5** 斑马鱼小鼠双敲除各支持何结论。关系核对：抗病、保守性、遗传机制有不同证据范围；源TXT锚点：p003, p005。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-07　浙江海宁“非遗双子星”闪耀海外

- ID：`zh-mct_local-6a04512f597f`；领域：社会与文化；拟适用维度：D1, D3, D4, D5, D6。
- [来源正文](https://www.mct.gov.cn/whzx/qgwhxxlb/zj/202607/t20260722_966650.htm)；页面日期2026-07-22；全文1748汉字数（longer），拟呈现1748（longer）。
- 时间、范围与缺口：官网2026-07-22；名单和5—6月老挝活动可能先公开，地方原稿待查。2016/2019/2023留背景，完整策略叙事。
- 最早观察到的公开证据：2026-07-22，[证据来源](https://www.mct.gov.cn/whzx/qgwhxxlb/zj/202607/t20260722_966650.htm)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement/snapshots/zh-mct_local-6a04512f597f.txt)；源簇建议`haining-heritage-global-dialogue-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D3** 静动组合数字复用青年参与各解决什么问题。关系核对：辨识度、地域次数限制、传承队伍各自对应；源TXT锚点：p003, p007, p010。
- **D4** 80后90后传承人合计多少。关系核对：12＋4=16；省级和市级为子集不重复相加；源TXT锚点：p013。
- **D5** 单次演出与持续传播有何差别。关系核对：归档复用和常态合作提供持续性；源TXT锚点：p009, p011。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-08　浙江“没有围墙的文化馆”渐成风尚

- ID：`zh-mct_local-f4d9389d2865`；领域：社会与文化；拟适用维度：D1, D2, D3, D4, D6。
- [来源正文](https://www.mct.gov.cn/whzx/qgwhxxlb/zj/202610/t20261009_967308.htm)；页面日期2026-10-09；全文1572汉字数（longer），拟呈现1572（longer）。
- 时间、范围与缺口：官网2026-10-09；多年实践与累计数据更早稿待查。完整三节结构，不把项目理念单独当新知识。
- 最早观察到的公开证据：2026-10-09，[证据来源](https://www.mct.gov.cn/whzx/qgwhxxlb/zj/202610/t20261009_967308.htm)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement/snapshots/zh-mct_local-f4d9389d2865.txt)；源簇建议`zhejiang-unwalled-culture-house-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D2** 围墙的实体与理念含义是什么。关系核对：坐等上门造成供需壁垒；源TXT锚点：p005。
- **D3** 盲盒音乐会和音乐任意门的群众角色如何不同。关系核对：送专业演出与交出舞台两种参与；源TXT锚点：p011。
- **D4** 4000余人抢30名额给出什么竞争下界。关系核对：超过约133.3人/名额，不能给精确值；须合适容差或选择题；源TXT锚点：p013。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-09　2026年秦岭生态保护监管跨区域协同座谈会在十堰召开

- ID：`zh-mee-161477ffc17c`；领域：环境与能源；拟适用维度：D1, D2, D3, D6。
- [来源正文](https://www.mee.gov.cn/ywdt/hjywnews/202609/t20260903_1165070.shtml)；页面日期2026-09-03；全文525汉字数（short），拟呈现525（short）。
- 时间、范围与缺口：官网2026-09-03；8月25日是事件日期，不是公开日期。完整短文；同会议更早稿和平台发布查重。
- 最早观察到的公开证据：2026-09-03，[证据来源](https://www.mee.gov.cn/ywdt/hjywnews/202609/t20260903_1165070.shtml)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-mee-161477ffc17c.txt)；源簇建议`qinling-cross-region-coordination-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D2** 平台上线计划出台加分细则是否都已完成。关系核对：上线已发生，计划/加分仍要求研究；源TXT锚点：p001, p002, p003。
- **D3** 边界不连续持续监管主动发现各对应什么措施。关系核对：一致性、遥感线索与考核激励各解决不同问题；源TXT锚点：p003。
- **D6** 主动发现问题精确加几分。关系核对：政策方向不提供精确分值；源TXT锚点：p003。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### ZH-10　旅游市场强制消费问题典型案例（2026年第六批）

- ID：`zh-mct-2310a232a3eb`；领域：公共政策；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://www.mct.gov.cn/whzx/whyw/202609/t20260911_967122.htm)；页面日期2026-09-11；全文2877汉字数（above_target），拟呈现1925（longer）。
- 时间、范围与缺口：官网2026-09-11，案件1—7月可能有地方原通报。建议引言+前8案完整p001—p017（1925汉字）；旧法律不当新答案。
- 最早观察到的公开证据：2026-09-11，[证据来源](https://www.mct.gov.cn/whzx/whyw/202609/t20260911_967122.htm)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/zh-mct-2310a232a3eb.txt)；源簇建议`mct-coercive-consumption-cases-2026-series`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** 求案例一二旅行社罚款差并区分个人罚款。关系核对：31000−30000=1000元；个人2000元不混主体；源TXT锚点：p003, p005。
- **D3** 案例五六低价游获利与处罚差别。关系核对：购物返点/自费获利和停业/吊销不同；源TXT锚点：p011, p013。
- **D6** 案例五购物总额或违法所得确数是多少。关系核对：60×51仅团费，不能推出购物额；源TXT锚点：p011。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

## 英文10篇

### EN-01　NASA’s SpaceX 35th Commercial Resupply Mission Overview

- ID：`en-nasa-1992c310d7b6`；领域：科学技术；拟适用维度：D1, D2, D3, D6。
- [来源正文](https://www.nasa.gov/general/nasas-spacex-35th-commercial-resupply-mission-overview/)；页面日期2026-10-07；全文587regex英文词数（含数字）（medium），拟呈现565（medium）。
- 时间、范围与缺口：API date 2026-10-07、modified 10月8日；实验更早披露待查。复用已有devpilot节选，不用实际发射事后更新计划快照。
- 最早观察到的公开证据：2026-10-07，[证据来源](https://www.nasa.gov/general/nasas-spacex-35th-commercial-resupply-mission-overview/)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-nasa-1992c310d7b6.txt)；源簇建议`spacex-crs-35-mission-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。
- 复用现有8道AI草稿，0人工。

可出题方向（不是冻结题/金标）：

- **D3** Match four experiments to mechanisms and purposes。关系核对：Retina layers, vascular networks, glass and brain diversity are distinct pairs；源TXT锚点：p007, p008, p010。
- **D2** Separate launched, empty support and returned hardware。关系核对：Empty clamshell returns a failed joint, not new joint delivery；源TXT锚点：p014, p016。
- **D6** Ask actual launch time or restored patient count。关系核对：Plans and potential benefits do not prove outcomes；源TXT锚点：p001, p007。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-02　NASA Model Wing Lights Up During First Pressure Sensitive Paint Tests

- ID：`en-nasa-2b3fb9c367c3`；领域：科学技术；拟适用维度：D1, D2, D3, D5, D6。
- [来源正文](https://www.nasa.gov/centers-and-facilities/langley/nasa-model-wing-lights-up-during-first-pressure-sensitive-paint-tests/)；页面日期2026-10-02；全文318regex英文词数（含数字）（short），拟呈现280（short）。
- 时间、范围与缺口：API 2026-10-02；旧压力漆原理与本次组合分开。保留完整六段，推荐区不呈现，首组合更早披露待查。
- 最早观察到的公开证据：2026-10-02，[证据来源](https://www.nasa.gov/centers-and-facilities/langley/nasa-model-wing-lights-up-during-first-pressure-sensitive-paint-tests/)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-nasa-2b3fb9c367c3.txt)；源簇建议`nasa-langley-unsteady-psp-free-model-test-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D2** Why does the benchmark not model one aircraft?。关系核对：Universal model for simulations；源TXT锚点：p003。
- **D3** Connect pressure, brightness, camera and simulations。关系核对：Brightness responds to pressure; captured changes feed models；源TXT锚点：p004。
- **D5** Separate first-use conditions and future applications。关系核对：Large-scale free motion and low oxygen; flexible models are prospective；源TXT锚点：p005, p006。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-03　About a Third of Workers Who Used AI in the Last Week Said They Completed Tasks One to Two Hours Faster

- ID：`en-census-8b06d9bbd7de`；领域：经济与产业；拟适用维度：D1, D2, D4, D5, D6。
- [来源正文](https://www.census.gov/library/stories/2026/08/ai-use-at-work.html)；页面日期2026-08-11；全文1002regex英文词数（含数字）（longer），拟呈现1002（longer）。
- 时间、范围与缺口：网页2026-08-11，正文9月24日权重修订；March 2026表包/PUF更早时间待查。锁定修订快照，保留分母及统计限制。
- 最早观察到的公开证据：2026-08-11，[证据来源](https://www.census.gov/library/stories/2026/08/ai-use-at-work.html)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement-environment-economy/snapshots/en-census-8b06d9bbd7de.txt)；源簇建议`htops-march-2026-ai-use-work-revised`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** Compute education-group gap for interpreting task。关系核对：46−15=31 percentage points, correctly named groups；源TXT锚点：p024。
- **D2** Does 31% saving hours refer to all workers?。关系核对：Only last-week AI users received time-saving question；源TXT锚点：p004, p018, p019。
- **D5** What changed in revision and what did not?。关系核对：Weights changed estimates, not testing conclusions；源TXT锚点：p001。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-04　Median Household Income in 2025 Surpassed Previous Highs Before and After the COVID-19 Pandemic 

- ID：`en-census-be20ba82c0cc`；领域：经济与产业；拟适用维度：D1, D3, D4, D5, D6。
- [来源正文](https://www.census.gov/library/stories/2026/09/median-household-income.html)；页面日期2026-09-15；全文520regex英文词数（含数字）（medium），拟呈现520（medium）。
- 时间、范围与缺口：官网2026-09-15称当日发布2025收入报告；报告与新闻同簇。保留税前税后通胀调整和显著性限制，改版待查。
- 最早观察到的公开证据：2026-09-15，[证据来源](https://www.census.gov/library/stories/2026/09/median-household-income.html)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement-environment-economy/snapshots/en-census-be20ba82c0cc.txt)；源簇建议`census-income-united-states-2025-release-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** Compute pre-/post-tax 2025 median gap。关系核对：87460−76060=$11400; not an individual tax bill；源TXT锚点：p001, p006, p009, p020。
- **D3** Why one record high but not post-tax?。关系核对：Post-tax below stimulus-supported 2020/2021; different series；源TXT锚点：p009, p010。
- **D5** Were 1967 percentile comparisons significance-tested?。关系核对：Unavailable margins of error prevent testing；源TXT锚点：p016。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-05　NIH launches new PubMed tool to strengthen research replication and reproducibility 

- ID：`en-nih-88aa9c4bbbb9`；领域：健康与生命科学；拟适用维度：D1, D2, D3, D6。
- [来源正文](https://www.nih.gov/news-events/news-releases/nih-launches-new-pubmed-tool-strengthen-research-replication-reproducibility)；页面日期2026-09-24；全文646regex英文词数（含数字）（medium），拟呈现646（medium）。
- 时间、范围与缺口：NIH2026-09-24，正文声明工具首个公开版；全球最早介绍未知。医学研究信息基础设施稿，体裁不当临床实验。
- 最早观察到的公开证据：2026-09-24，[证据来源](https://www.nih.gov/news-events/news-releases/nih-launches-new-pubmed-tool-strengthen-research-replication-reproducibility)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-nih-88aa9c4bbbb9.txt)；源簇建议`nlm-linked-discoveries-first-public-version-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D2** Does tool certify replication or quality?。关系核对：Organizes context; researchers make assessments；源TXT锚点：p006, p008。
- **D3** Connect search problem to graph/timeline filters。关系核对：Dispersed and prominence-biased sources motivate connected neighborhoods；源TXT锚点：p003, p005。
- **D6** Ask measured replication-detection precision。关系核对：No such validation metric and no promised quality judgement；源TXT锚点：p006。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-06　Deep learning model using ECGs during sleep studies can predict cardiovascular outcomes

- ID：`en-nih-63b73a8c608a`；领域：健康与生命科学；拟适用维度：D1, D2, D4, D5, D6。
- [来源正文](https://www.nih.gov/news-events/news-releases/deep-learning-model-using-ecgs-during-sleep-studies-can-predict-cardiovascular-outcomes)；页面日期2026-10-09；全文700regex英文词数（含数字）（medium），拟呈现700（medium）。
- 时间、范围与缺口：NIH和SLEEP2026-10-09；稿件2026-01-27收到，有限检索无更早同稿，不穷尽。保留训练/验证分工、结局限制，不问未给AUC。
- 最早观察到的公开证据：2026-10-09，[证据来源](https://academic.oup.com/sleep/advance-article/doi/10.1093/sleep/zsag229/8885715)（publisher_page_read；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-nih-63b73a8c608a.txt)；源簇建议`doi-10.1093-sleep-zsag229`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** Sum external validation and compare fine-tuning size。关系核对：9810+12576=22386, gap6577; validation is not training；源TXT锚点：p006。
- **D2** Separate supported and still unoptimized outcomes。关系核对：AF/HF/death versus MI/stroke；源TXT锚点：p007, p008。
- **D5** Does adjusted prediction establish clinical benefit?。关系核对：Association is supported; traditional-risk improvement needs evaluation；源TXT锚点：p004, p007。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-07　The American Folklife Center Turns 50: See the New Exhibit | Timeless

- ID：`en-loc-359fbdc1a252`；领域：社会与文化；拟适用维度：D1, D2, D3, D5, D6。
- [来源正文](https://blogs.loc.gov/loc/2026/09/the-american-folklife-center-turns-50-see-the-new-exhibit/)；页面日期2026-09-21；全文1403regex英文词数（含数字）（above_target），拟呈现1374（longer）。
- 时间、范围与缺口：博客2026-09-21且同刊9/10月杂志，更早杂志上线待查。历史大量旧，仅问本次策展关系；可完整移作者前言到署名区控1400词。
- 最早观察到的公开证据：2026-09-21，[证据来源](https://blogs.loc.gov/loc/2026/09/the-american-folklife-center-turns-50-see-the-new-exhibit/)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-loc-359fbdc1a252.txt)；源簇建议`afc50-alive-in-many-hands-exhibit-magazine-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D3** Connect certificate foodways oral histories to exhibit theme。关系核对：Practices, community and memory need multiple sections；源TXT锚点：p007, p016, p019, p020, p024。
- **D2** Distinguish artifact dates and exhibit duration。关系核对：Old items do not date opening; early2028 is approximate；源TXT锚点：p005, p018。
- **D5** How final recording story supports mission。关系核对：Archives connect living descendants with memory；源TXT锚点：p036, p037。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-08　Helping Homeless Kids with Reading: Brazil’s Projeto Uerê Wins Library’s Top Literacy Award | Timeless

- ID：`en-loc-829b92bd1e91`；领域：社会与文化；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://blogs.loc.gov/loc/2026/09/helping-homeless-kids-with-reading-brazils-projeto-uere-wins-librarys-top-literacy-award/)；页面日期2026-09-14；全文500regex英文词数（含数字）（medium），拟呈现500（medium）。
- 时间、范围与缺口：博客2026-09-14，International Literacy Day已宣布，正式名单更早待核。1980/1993留背景，新题为本届奖项。
- 最早观察到的公开证据：2026-09-14，[证据来源](https://blogs.loc.gov/loc/2026/09/helping-homeless-kids-with-reading-brazils-projeto-uere-wins-librarys-top-literacy-award/)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-loc-829b92bd1e91.txt)；源簇建议`loc-literacy-awards-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** Sum named prizes and subtract from overall total。关系核对：150+100+50+50=350k;495−350=145k, no equal-share assumption；源TXT锚点：p005, p008, p011。
- **D3** Compare Read Alliance and Uere beneficiaries。关系核对：K2 readers, teen tutors and trauma-impaired learners benefit differently；源TXT锚点：p004, p007, p012。
- **D6** Ask each17 honorees exact payment。关系核对：Aggregate cannot determine each；源TXT锚点：p008。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-09　New USGS-Funded Science Will Support Landslide Public Safety and Disaster Preparedness Nationwide

- ID：`en-usgs_release-8091ff19244f`；领域：环境与能源；拟适用维度：D1, D3, D4, D6。
- [来源正文](https://www.usgs.gov/news/state-news-release/new-usgs-funded-science-will-support-landslide-public-safety-and-disaster)；页面日期2026-09-10；全文442regex英文词数（含数字）（medium），拟呈现442（medium）。
- 时间、范围与缺口：主文日期2026-09-10，授奖清单和地方公告更早待查。16受助方不是16州，旧法案/旧项目留背景。
- 最早观察到的公开证据：2026-09-10，[证据来源](https://www.usgs.gov/news/state-news-release/new-usgs-funded-science-will-support-landslide-public-safety-and-disaster)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-supplement-usgs/snapshots/en-usgs_release-8091ff19244f.txt)；源簇建议`usgs-landslide-grants-fy2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D4** Compute average funding and limit inference。关系核对：1m/16=$62500 arithmetic average, not equal grants；源TXT锚点：p002。
- **D3** Match recipient geography and products。关系核对：Tribal partnership, county inventory, statewide/postfire and improved mapping differ；源TXT锚点：p005, p006, p007, p008。
- **D6** Ask exact grants or expected casualties prevented。关系核对：Allocation and quantified safety outcomes absent；源TXT锚点：p002。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

### EN-10　£100 million competition to back British AI companies to fix public services

- ID：`en-govuk-d5865b812982`；领域：公共政策；拟适用维度：D1, D2, D3, D6。
- [来源正文](https://www.gov.uk/government/news/100-million-competition-to-back-british-ai-companies-to-fix-public-services)；页面日期2026-08-31；全文1073regex英文词数（含数字）（longer），拟呈现1073（longer）。
- 时间、范围与缺口：官方API first_published2026-08-31仅该页首发；预算/方案更早待查。完整稿保留技术阶段、条件预付、IP与挑战分工。
- 最早观察到的公开证据：2026-08-31，[证据来源](https://www.gov.uk/government/news/100-million-competition-to-back-british-ai-companies-to-fix-public-services)（local_snapshot_page_date_only; prior_version_search_pending；全球最早未知）。
- [本地正文](../data/candidates/20261011-source-discovery/snapshots/en-govuk-d5865b812982.txt)；源簇建议`sovereign-ai-rd-procurement-first-competitions-2026`尚未审定；全球首发、实际训练见过与题级答案新颖性仍未知。

可出题方向（不是冻结题/金标）：

- **D2** Does scheme target basic research and take firms IP?。关系核对：Demonstrator-stage beyond early research; firms retain IP；源TXT锚点：p016, p024, p028。
- **D3** Connect barriers to payments and early customers。关系核对：Cash/track-record and prototype-to-customer transition; payments where appropriate；源TXT锚点：p015, p024。
- **D6** Are four challenges guaranteed £25m each?。关系核对：100m total plus4 challenges does not prove equal allocation；源TXT锚点：p002, p004, p019。

后续逐题核查答案新颖性、必需证据、别名/单位/容差和维度；真实双人审题与仲裁后才冻结。

## 开发/测试隔离与后续动作

1. 20篇及其全文、节选、译文、同论文/同事件稿只留开发；源簇待人工复核。机器清单为零售月报、强制消费案例系列保守列出候选阻断名单；不是完成全部402篇语义去重。
2. 先编可运行的小批新增题；已有16题继续按统一协议审题。目标每篇6可答＋2合理缺信息，全库覆盖六维，不强迫每篇有计算条件。
3. 锚点是源TXT按空行分段的1起始索引，不是冻结bank段落ID。实际节选、稳定ID、输入hash与金标证据链须一起保存。
4. Census AI调查已有9月24日修订，保留正文版本和权重注记；不得混8月旧数值。NASA任务预测按冻结快照，不用后续真实事件替换答案。
5. 对所有拟入选题继续查原稿/预印本/数据包；阴性搜索不证明无污染。真实审题人、独立复核和仲裁记录不能由AI代填。
6. 正式100篇仍需更均衡来源/体裁配额以及适当新信息，开发选择不替代正式配额。

备选FAST三体脉冲星已有[2026-08-02 arXiv v1](https://arxiv.org/abs/2608.01227)，仍晚于模型，可补采编；长江署名稿约4147汉字需要谨慎节选和旧背景筛查。
