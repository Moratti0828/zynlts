# CHANGE-002：补充可校准、只读的证据审查与故障演练

类型：2026-11-17本组自主改进；不是对抗组正式出题。基线Git：d80c5f9。动机：课件评价器15分中的项目适配和校准此前只有文档计划，没有可运行工具。

范围：新增scripts/review_evidence.py、tests/test_evidence_reviewer.py、course_defense_drill.py；verify_course加入演练检查。数据、评分规则、模型API、数据库结构不变，无迁移。

验收：同版本可核查断言有限PASS；反例FAIL；缺证据INSUFFICIENT_EVIDENCE；仅预批准项N/A。拒绝错ID/版本/hash/越界和超大输入；不执行目标文本指令。四类已知故障被既有产品测试检出，并在恢复后通过。

实测失败：evidence/rubric-20261117/drill/result.json，M2漏检。根因：Python的from-import保留旧函数绑定，模块属性patch未改变测试的直接调用。影响为演练不具有所声称的故障覆盖；不是已证实的线上评分错误。

修复：选择经benchmark_v2.grade走模块全局函数的已有负向用例。复核：drill-corrected/result.json，4/4检出；每个故障的baseline/known_bad/restored日志均保留。校准与恢复共12项通过，后续全量回归由新的verification目录记录。

回滚：Git revert此改进提交即可；停止把新增演练加入verify入口，产品功能与历史实验不受影响。禁止为了“全绿”删除首次失败记录。伙伴签署状态pending；具体结果由伙伴自己的运行产生。
