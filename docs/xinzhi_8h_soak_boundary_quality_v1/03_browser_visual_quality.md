# 03 浏览器视觉质量专项

强制入口：`http://127.0.0.1:8000/workspace`

检查：
- 标题/段落/列表/表格/代码块
- Markdown
- LaTeX/KaTeX 行内与块级
- 资料卡片
- 多图顺序
- Circuit SVG / Artifact
- warning/loading/error/review
- 历史恢复
- 长回答滚动和卡顿

禁止普通页面突出 agent_id、handler_id、runtime generation、raw error、provider internals。

长回答测试：1k / 3k / 5k+ 字。

至少窗口：1920×1080、1440×900、1366×768；如支持 dark/light 两者均检查。

重要视觉缺陷记录 case id、截图、窗口尺寸、task id。

评分：A 产品级 / B 可接受 / C 明显瑕疵 / D 破版不可用。
目标 A+B >=95%，D=0。

输出：
`docs/audit/69_browser_visual_quality_report.md`
