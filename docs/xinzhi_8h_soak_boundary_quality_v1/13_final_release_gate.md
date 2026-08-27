# 13 最终 Release Gate

必须证明 soak >= 8h；如中途发生重大执行逻辑修复，必须追加 soak。

硬门槛：
legacy invocation = 0
execution drift = 0
registry drift = 0
completed-without-result = 0
browser infinite loading = 0
cross-session leakage = 0
silent image drop = 0
formula whole-answer failure = 0
circuit renderer causing solver failure = 0

质量：
browser visual A+B >=95%
ordinary semantic A+B >=95%
hard semantic A+B >=90%
same-question core consistency >=95%

Circuit：
OFF regression=0
artifact visibility=100% when render succeeds
critical topology silent error=0
AUTO false-positive controlled

资源：
不得出现持续内存泄漏、连接池泄漏、running task 单调增长、lease 残留增长、明显 latency drift。

最终浏览器回归至少：
20 general
20 solver
10 single-image
10 multi-image
10 RAG
10 Circuit
5 long sessions

输出：
`docs/audit/79_8h_soak_final_report.md`
`docs/audit/80_long_run_stable_baseline.md`
