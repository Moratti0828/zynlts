# 8分钟展示与个人练习

这是一份练习提纲，不是已完成的个人答辩记录。先用自己的话练，再打开对应代码/原始结果；不知道的地方说明未验证。

## 展示顺序

| 时间 | 要解释的内容 | 打开的证据 |
|---|---|---|
| 0:00—1:00 | 平台解决什么问题、适用范围与三个不变量 | Global.md、specification.md |
| 1:00—2:30 | 请求从创建到导出的路径；金标为何不会发给模型 | backend/experiment_v2.py的create_run/messages/execute_run；test_public_prompt_does_not_leak_gold_or_review_metadata |
| 2:30—4:00 | 现场一次故障演练：正常通过→故障被抓→恢复通过 | 运行下方drill，打开M3或M4三段日志 |
| 4:00—5:00 | 一次恢复：已完成项不重复，外部未知请求留attempt | test_unknown_inflight_attempt_survives_resume_and_new_result_is_linked；drill输出 |
| 5:00—6:00 | 工程实验的比较与成本；为什么不能推断整个系统提速 | EXP-001六条运行、协议和ADR-002 |
| 6:00—7:00 | 评价器如何区分已知失败、缺证据和不适用 | review/evaluator；K2/K3/K5/K6测试 |
| 7:00—8:00 | 本人责任、限制、对抗组下一步 | AI披露、peer-plan、此轮未完成人审/交叉复现 |

```sh
.venv/bin/python scripts/course_defense_drill.py --output evidence/my-live-rehearsal
```

该命令不下载模型，不接触真实数据库；固定白名单本地测试，注入只存在内存，记录明确写作模拟。若老师要求真实推理，需预先准备模型服务；无模型时说明只演示工程路径，不能拿模拟回答冒充推理。

## 五道自测题（先答再核验）

1. 一题正确、一题超时，准确率是多少？为什么不能只统计成功题？核验test_request_errors_remain_in_accuracy_denominator。
2. “red red red blue”对“red blue”的F1为什么是2/3？词序/否定变化为何不能只看F1？核验test_benchmark_v2.py。
3. 输入恰好达到预算和多1 token时分别怎样？能否直接截断正文？核验test_token_budget.py的test_boundary_and_no_truncation。
4. 请求已发出但服务重启，为什么不能说“没执行过”？续跑怎样保留原attempt？核验experiment_v2.resume_run及对应测试。
5. 看到记录的status=PASS，凭什么只能给STATIC？如何才算伙伴REPRODUCED？解释Hash完整性与来源真实性的差别。

## 可练的现场变更

练习A：把预算fixture减1，先写预期拒绝，再运行，最后恢复。练习B：增加一个否定词，比较严格答案与词重叠F1；说明为什么不能修改金标迁就输出。练习C：构造错版本证据，预测评价器的状态及最小补查。

每次自己记：初始commit、预判、实际操作、结果路径、差异原因、如何恢复、用时。不要直接将此提纲填为“已独立完成”。单人组不虚构两人轮换，老师如要求实现/核查阶段说明，可展示本人分时完成的真实记录。
