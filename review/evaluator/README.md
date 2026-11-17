# 受限评价工作流 v1

对应项目课件第78—93页及附录G的“评价Agent与交叉审查”：项目适配、校准/错误分析、实际复核、权限隐私。这里提供确定性预检＋当前Codex会话的一次有范围语义复核；不是新增自治Agent平台，不是假装完成同伴交叉审查。

## 运行与信任边界

```sh
.venv/bin/python scripts/review_evidence.py --root . --contract review/evaluator/local-contract.json --output evidence/my-precheck.json
.venv/bin/python scripts/course_defense_drill.py --output evidence/my-drill
```

预检仅读取每个不超过2MiB的JSON，禁止路径越界/越界符号链接，不访问URL、不执行目标脚本、不加载AGENTS/hooks、不调用模型。契约由审查者从受控目录明确指定；`local-contract.json`只是本组提议，未获得教师批准，不能让目标组README替换它。真正评同伴时需由双方/教师确认契约与版本，再准备只读快照。

预检检查ID、版本、Hash、字段类型与固定断言；结果为PASS/FAIL/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE。PASS只支持该字段断言；Hash不能认证执行来源。N/A须有契约批准项及引用，工具无法自动认证批准人的真实性。`declared_origin`是材料自述，实际检查层级始终STATIC，不能因为有人写peer_runner就升级为REPRODUCED。

本轮适配三项：历史测试包状态、评分实验输出一致性、校准与恢复演练状态。旧测试包对应其内的源Hash，本轮包版本不是旧代码版本。语义复核见semantic-review.json；报告评分建议为null，人工签署pending。

## 校准与错误分析

`tests/test_evidence_reviewer.py`：K1有限通过，K2明确失败，K3只有自述，K4诱导文本，K5虚构ID/错版本，K6预批准不适用；另含篡改、布尔/数字混淆、路径/符号链接/超大文件检查。K6的教师批准引用是明确标注的合成fixture，不是真实批准。

`evidence/rubric-20261117/drill-corrected/result.json`保存8项评价器测试＋4项恢复/幂等测试；4个故障各运行原实现、故障、恢复三次。故障为丢失数值符号、F1始终满分、预算校验绕过、金标泄漏。只在本进程内存注入，退出/恢复后不改变项目代码或历史数据。

首次 `drill/result.json` 检出3/4：M2测试先导入了函数引用，替换模块属性没有影响该引用，未真正击中测试调用路径。修订为经grade函数调用F1，明确注入生效后检出4/4。此处是演练适配问题，不得宣称发现产品本身“F1总满分”漏洞。失败记录不删除。

六个公开样例全过不等于评价器总体准确率100%，更不证明LLM抗注入。确定性层的校准与语义模型的校准分开：本轮没有多模型/保留集语义判读校准，未测费用与人工分钟填未知，实际伙伴复核待开展。
