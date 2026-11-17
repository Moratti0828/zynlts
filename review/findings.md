# 问题与回归记录

## SELF-001：默认Python过旧时启动错误不明确

类型：本组自查，非对抗组Finding。基线为接收的reading-bench快照；环境macOS默认Python3.9。运行 `python3 -m unittest discover -s tests -v`，live_demo的 `list | None` 在运行时产生TypeError；项目原声明要求3.11+，因此这是启动诊断/环境可复现性问题，不是支持版本上的评分缺陷。

修复：backend包在过旧Python下明确报3.11+；start.sh优先虚拟环境/可用新版；完整验收改用Python3.12。回归见 evidence/course-20261117/verification 及 startup-check.json。首次受沙箱限制不能绑定回环端口也明确保留为执行环境问题，不能伪装功能失败或测试通过。

## 伙伴Finding模板（未执行）

- ID / 提交者 / 日期：待实际填写
- 对方目标commit、契约版本、环境与前置条件：待填写
- 最小复现命令与输入hash：待填写
- 预期与实际：待填写
- 原始输出路径、影响与严重性：待填写
- 修复commit、回归命令和新结果：待填写
- 独立复核结论（PASS/FAIL/INCONCLUSIVE/NOT_APPLICABLE）及未查范围：待填写

没有对方源码及实测结果时不填写漏洞结论，不代对方签字。
