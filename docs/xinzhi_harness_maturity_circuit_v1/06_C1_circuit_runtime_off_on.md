# C1：Circuit Tool 接 Runtime，先 OFF / ON

这是第一次接生产链，必须最保守。

Feature Flags：
CIRCUIT_RENDER_ENABLED=false
CIRCUIT_RENDER_AUTO=false

第一阶段仅：
OFF
ON

OFF：
现有 Solver 完全不调用 circuit.render，行为必须等于 5cb699c baseline。

ON：
只有用户明确要求“画一下 / 重新绘制 / 画等效电路 / 生成电路示意图”时才允许调用。

禁止新增 CIRCUIT_DRAWING_AGENT。

推荐：
Solver
→ Solution / structured facts
→ CircuitIR
→ circuit.render

如果没有稳定 CircuitIR adapter，只增加最小 adapter，不改 Solver 主逻辑。

强制失败隔离：
Solver success + Renderer fail = Task success
必须返回完整答案 + 绘图失败提示。

Circuit render 使用独立短 timeout，不占 Solver provider timeout。

验收：
OFF：20 个已有 Solver baseline，0 行为退化。
ON：至少 10 个显式绘图请求成功触发 tool。

浏览器必须测试：普通 Solver、显式画图 Solver、图片题、追问。

提交：
`feat(circuit): integrate opt-in circuit render capability`

输出：
`docs/audit/51_circuit_runtime_integration_report.md`
