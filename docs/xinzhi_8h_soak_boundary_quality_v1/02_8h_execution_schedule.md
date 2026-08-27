# 02 至少 8 小时执行时间表

总持续时间 >= 8h，推荐 10~12h。

## Hour 0~1 基线与视觉
- health / fingerprint
- Golden cases 20
- 浏览器视觉第一轮
- LaTeX corpus 第一轮
- Circuit 10
- 记录 RSS、DB、Redis、p50/p95

## Hour 1~2 专业 Solver
CT/AE/DE/SS 每门至少普通10、困难5、边界5；检查答案、单位、符号、步骤、稳定性、LaTeX。

## Hour 2~3 多模态 + Circuit
单图15、双图10、三图10、4~5图5、Circuit render20。重点图片顺序、指代、图文冲突、CircuitIR、拓扑、Artifact、SVG 视觉。

## Hour 3~4 多轮/Memory/Session
至少 5×20 turns，混入纠错、方法切换、图片引用、Circuit 重画、RAG，并快速切换 Session。

## Hour 4~5 Restart/Recovery/Queue
API restart、worker restart、queued task、expired lease、cancel、retry、SSE reconnect、history restore；至少5个 restart cycles。

## Hour 5~6 六案例专项
教师备课、首错、学习路径、科研简报、知识治理、专业 Solver+Circuit；每个正常5、困难3、边界2。

## Hour 6~7 边界/故障/混合压力
极长 prompt、空白 follow-up、错别字、错公式、非标准 LaTeX、大表格、多附件、不支持文件、Provider timeout、RAG empty、Circuit invalid、Artifact fail、刷新、并发 Session。

## Hour 7~8 长期漂移
不重启，持续随机混合任务；每15分钟记录 fingerprint、registry hash、legacy counters、RSS、DB、running tasks、lease、latency、error rate。

## Hour 8+
若发现问题并修复，继续追加 1~2h mixed soak。重大执行层修复后不能把修复前时长直接视为最终稳定证明。
