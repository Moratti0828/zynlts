# 验收矩阵增补

READ-01—08 的 GWT 见 [原规格](../specification.md)。本轮保留原评分语义，增加下列要求。

| ID | Given / When / Then | 验证 |
|---|---|---|
| READ-09 | Python低于3.11 / 导入后端 / 明确报版本要求；支持版本正常启动 | backend/__init__.py；本轮启动检查记录 |
| READ-10 | 多参考别名与重复token / 候选F1评分 / 与保留原实现逐项完全一致 | test_short_f1_equivalence.py；EXP-001逐项输出 |
| READ-11 | 新机器与空状态 / 执行课程检查 / 不依赖旧数据库或本地权重，保留日志/退出码 | scripts/verify_course.py；CI |
| READ-12 | 已存在实验输出目录 / 重跑比较 / 拒绝覆盖；失败不能伪装PASS | compare_short_f1.py使用exist_ok=False；错误和状态写入result |

原规格对应的自动检查覆盖：READ-02/03/04/05/06/07见 test_contract.py；READ-08见test_experiment_v2.py、test_live_demo.py。READ-01的真实推理仅由历史run输出支持，本次离线测试中的fake模型不能计作真实调用。Python回归证据必须结合exit_code与日志看，不能只读报告结论。
