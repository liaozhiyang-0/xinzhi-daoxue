# 04 LaTeX / KaTeX Torture Test

建立 50~100 条电子信息真实复杂公式 fixture。

必须覆盖：
- 微积分、积分上下限、微分
- 求和、极限
- 矩阵、分段函数
- 相量、复数
- 傅里叶、拉普拉斯、Z 变换
- 卷积、概率、向量
- aligned 多行公式
- 中文+行内公式、中文+块级公式
- Markdown table 内公式
- 代码块、URL、日期、JSON 中的 `$`

错误 LaTeX：
missing brace、unsupported command、nested delimiter、unclosed `$`、Markdown 冲突。

要求：错误只能局部降级显示原始 LaTeX，不能破坏整条回答。

浏览器重点：inline baseline、block spacing、overflow、matrix clipping、窄窗口、dark mode、copyability。

硬门槛：
page crash=0
whole-answer render failure=0
formula silently missing=0

输出：
`docs/audit/70_latex_katex_torture_report.md`
