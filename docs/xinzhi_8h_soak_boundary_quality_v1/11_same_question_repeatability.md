# 11 同题重复稳定性

至少 30 questions × 5 repeats = 150 次。

分类：
文字 Solver、单图、多图、RAG、Circuit、General。

统计：
route consistency
runtime consistency
review consistency
degrade consistency
core answer consistency
numeric consistency
circuit topology consistency
latency variance

允许：措辞和解释顺序变化。
不允许：
一次有答案一次无答案
数值频繁变化
相同模式下一次画图一次不画
一次 waiting_review 一次 completed

目标：
core answer consistency >=95%
标准数值题 numeric consistency 尽量 >=98%

输出：
`docs/audit/77_repeatability_report.md`
