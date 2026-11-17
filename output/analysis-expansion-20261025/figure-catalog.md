# 图目录

所有图均来自已核验的真实导出；不填充虚构数字；PNG预览、PDF矢量版本。

## 图1：各bank/窗口/语言的任务表现

- 文件：figures/figure-01-bank-task-comparison.png及同名PDF。
- 解读：各面板独立显示题型点估计和适用题数。N/A表示未覆盖；面板材料不同，颜色或数值不能直接作跨bank/窗口能力排序。该图用于识别任务覆盖和待复核的错误方向；详细CI在数值表。
- 来源：numeric-table.json或paired-differences.json；上游导出及hash见metadata.json。
- 局限：单seed、人审0、来源簇暂定、小样本/高分CI可退化；无显著性或赢家声明。

## 图2：4K条件下相同题目的有文收益

- 文件：figures/figure-02-four-k-context-difference.png及同名PDF。
- 解读：差值为有文减无文，单位百分点，并列配对题数。只使用同一bank、模型、4K窗口下的同题交集；原始8K全量没有直接参与相减。正差支持本子集取得文本后有帮助，不能证明训练无污染或纯理解增益。
- 来源：numeric-table.json或paired-differences.json；上游导出及hash见metadata.json。
- 局限：单seed、人审0、来源簇暂定、小样本/高分CI可退化；无显著性或赢家声明。
