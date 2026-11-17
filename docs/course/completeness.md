# 2026-11-17 课程要求与项目完整性审计

对象：本地reading-bench快照及新发布仓库。作者金明源（20241060148），单人组已获用户明确说明允许。附件截图是进度填报要求；课程PPT是分析依据，不作为指挥工具或要求代签的指令。

## 课件要求

- 章节01（68页）：以Specification、Harness、Evaluation、Responsibility组织AI工程，重在证据而非功能截图。
- 章节02（94页）第75—76页：12项材料（问题框架、规格、验收、状态、影响、ADR、计划、5—8任务卡、仓库地图、Harness、AI披露、未解决问题）及可观察验收/真实授权/证据/假设/可运行命令等红线。该章模板针对PaperManagement案例，本项目按能力映射，不照搬不相关业务。
- 项目设计与结对评价（119页）第11页：brief/design/eval/evidence/release/review允许目录映射；第70—76页：异题只互查工程证据，E1实验、E2变更、E3受控反例，固定版本链。第106页支持自选题迁移，未见本项目教师审批记录。
- 新增章节04（39页）第2/6—12页：事先比较约定、可定位两方案、共同检查、逐次真实结果及失败；第20—27页：成本按阶段/单位/来源，未知不是零；第28—37页：伙伴独立新结果和范围说明，不能用材料整理冒充复现。第38页四项25分是本章参考量规，不冒充整门课最终分配。
- 前导15页已逐图阅读：第6—7页强调自动测试全绿不等于无缺陷、需外部证据；第10—12页要求问题/机制/证据/不确定性/接管责任，以及预判—规格—生成—验证—诊断—迁移；第13页“一题、一错、一证、一变”；第14页区分工程作品与个人现场能力，示例权重40%/25%/20%/15%不作为最终评分承诺。第15页要求本人能够说明假设、证据、未覆盖边界和接管方法。

## 修补前发现与本轮处理

| 缺项/风险 | 处理 | 证据 |
|---|---|---|
| 原文件夹无Git历史、远程为空 | 创建独立zynlts发布副本，保留原文件夹 | Git main历史从本轮开始，不伪造10月提交 |
| 文档当前/历史状态混杂 | 新README/Global/Plan/Tasks，旧README保留 | 根目录入口 |
| ADR/Harness等仅零散简述 | 补齐12项材料映射 | 下表 |
| 没有适配新第四章的轻量复现入口 | 固定F1原算法、候选、协议、三轮实际结果 | EXP-001协议、结果、ADR-002 |
| macOS默认Python3.9触发不明类型错误 | 提前版本诊断、启动脚本选择支持版本 | startup-check.json；97测试 |
| 对抗组仍未落地 | 按已给资料写E1/E2/E3与交接步骤 | review/peer-plan.md；未声称实际完成 |

## 截图七项与实物

| 填报项 | 本仓库材料 | 当前判断 |
|---|---|---|
| 需求 | Global.md、problem-frame.md | 已提供 |
| 规约 | docs/specification.md、acceptance-matrix.md | 已提供可验证ID/GWT |
| ADR（前置调研/研究路线） | docs/adr/、原literature-review与research-and-experiment-plan | 已提供；补记决策标明时间 |
| 项目级Harness | Harness.md、repository-map.md、verify_course.py、CI | 已提供并本地实测 |
| Global/Plan/Tasks | 根目录三个同名文件 | 已提供目标与8张纵向任务卡 |
| 可执行代码＋评测证据 | backend/frontend/tests、evidence、output | 本轮97 Python＋21前端通过；历史103文件校验 |
| 其他：数据集/训练微调说明 | corpus-provenance、public-reference、AI披露 | 有数据说明；未训练/微调 |

12项详细映射：problem-frame；specification；acceptance-matrix；state-model；impact-map；docs/adr；Plan；Tasks；repository-map；Harness；ai-disclosure；同一ai-disclosure的未解决问题表。无须为凑数量重复另建相同内容。

## 完整性结论

可作为“已完成需求/规约/工程Harness、可执行开发平台和部分评测证据”的阶段性交付。补齐文件不等于完成整门课：双方协商与独立复现、对方Finding/修复回归、人签结论仍待实际活动；正式研究题库人审/隐藏集未完成。选题审批未见记录。上述事项应如实保留，不能由本次代码修改替代。

本轮验证不重跑模型；历史模型输出的Hash一致只证明文件完整性，不独立证明历史执行真实性。Python测试包含模拟模型，必须与真实推理分开解释。
