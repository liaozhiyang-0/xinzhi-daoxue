# 09 长对话、Session 与纠错压力

至少 10 sessions：
5×20 turns
3×30 turns
2×40 turns

一个 Session 内混入：
Solver、图片、RAG、Circuit、回答风格变化、用户纠正、方法切换。

Correction Case：
Turn2 R2=10Ω
Turn15 用户纠正 R2=20Ω
Turn31 重新计算
必须使用 20Ω。

Session A/B/C 快速切换，cross-session leakage=0。

Circuit follow-up：
- 刚才那个等效电路重新画一下
- 只画第二种方法
- 第二张图的 R3 改成20Ω后重画

同时检查 compaction 后是否保留最新条件、图片引用、当前方法和回答模式。

输出：
`docs/audit/75_long_context_session_report.md`
