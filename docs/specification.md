# Specification v1.0 / Project Teaching Fit Card

2026-11-17增补：本文件保留首版需求，当前v2状态/恢复语义以 [状态模型](course/state-model.md) 和 [验收增补](course/acceptance-matrix.md) 为准。作者金明源（20241060148），单人组获准；伙伴独立签署仍未执行。

## Intent 与范围

给学生和评测者一个现场可操作的工具，用近期文章测试早期固定模型依据文本作答的表现，保存每个结果的来源和运行身份。

流程：选材料和模型 → 执行真实推理 → 查看确定性评分并导出证据。首版不训练模型，不用自动联网/RAG，不裁决人的阅读能力，不用另一模型自动给最终真值，不承诺长上下文或绝对无污染。

## 三条不变量

1. 受试模型输入不包含参考答案与金标证据，只包含题目、实际节选和固定指令。
2. 未执行、失败、格式错误和模型版本变化不伪装为有效完成；失败保留并影响EM/F1分母。
3. 每个实验有固定的文章/问题/模型/配置快照；新导入或新跑实验不修改旧结果。

## 验收矩阵

| ID | MUST要求 | Given / When / Then | 验证证据 |
|---|---|---|---|
| READ-01 | 真正请求模型并保存响应 | 已安装模型 / 发起4题 / 返回逐题raw_response、耗时与run ID | 本机真实run JSON；截图只用于界面 |
| READ-02 | 日期和模型版本可追踪 | 选择文章与固定digest / strict运行 / 原始发布日期声明严格更早且digest匹配，否则拒绝 | `test_model_date_and_unpinned_versions_are_rejected`；run snapshot |
| READ-03 | 不泄漏gold | 题库含私有参考答案 / 构造模型请求 / messages不存在gold字段 | `test_gold_answer_and_evidence_never_sent_to_model` |
| READ-04 | 金标有可核对证据 | 导入损坏hash或不存在证据 / POST文章 / 拒绝且不入库 | `test_corpus_rejects_corrupted_hash_and_nonexistent_evidence` |
| READ-05 | 错误答案不得得满分 | Good/错城市/数字负号百分比 / 评分 / 正误可区分 | GraderContract正例与Known Bad |
| READ-06 | 运行失败不能删分母 | 1成功1超时 / 汇总 / EM=.5，失败数=1 | `test_request_errors_remain_in_accuracy_denominator` |
| READ-07 | 输出格式错误不得冒充拒答 | 非JSON/字符串布尔/NaN / 解析 / 明确失败 | `test_malformed_response_does_not_become_success` |
| READ-08 | 结果可导出和恢复 | 完成实验 / JSON与CSV导出 / 快照、raw、指标完整；重启不自动重复请求 | 实际HTTP导出与SQLite检查 |

## Harness 与ADR

Runtime Harness：单工作线程串行模型调用，每请求180秒上限、任务队列上限3、取消后不再启动下题；模型版本变化停止；服务重启把未完成任务标为interrupted。

Project Harness：本README为Repository Map；`python -m unittest discover -s tests -v`是机械验证入口；固定corpus.json、prompt/grader版本、完整digest与run快照是证据来源。服务无外部检索工具，采集脚本只产出隔离候选。

ADR-01：使用Python标准库HTTP/SQLite和原生前端，减小同学复现的依赖成本。代价是首版单机串行、无多用户权限体系，不适合公网多租户。部署可用Ollama与独立容器，未来吞吐需求再评估vLLM。

恢复：先停止应用再备份var目录，保留题库及模型清单；重新启动不恢复未完成请求，另建实验重跑。停止条件：连接/版本变化、取消、输出预算、请求超时；服务器条件不足则保持本地演示，真实服务器尚未上线不写PASS。

## 课程迁移与责任

O1：人定义研究问题，AI产生实现与候选题，人负责来源、金标和结论。O2：READ-01至08。O3：run ID、hash、raw与分母。O4：有/无文本条件的成本和正确性。O5：导入新文章与受控错误证据。O6：零依赖启动、备份、部署说明。O7：明确污染和小样本边界，各成员轮换实现和验证。

四状态审查可用PASS/FAIL/INCONCLUSIVE/NOT_APPLICABLE，但当前没有额外自治评价Agent。测试通过仅支持这些具体验收，不能外推为“平台全方面安全”或“科学结论已获证明”。

用户与搭档签署：待填写。独立人工审题：待执行。教师自选题认可：待确认。服务器连接与GPU信息：已按使用指南实际核查，部署证据见verification.md。
