# C0：Circuit Rendering Standalone Baseline

先把现有 `apps/api/app/circuit/` 当独立领域工具验收，不接 Solver。

复用：
CircuitIR → Validator → Layout → Renderer → CircuitRenderResult

禁止新建平行 Circuit schema。

测试至少覆盖：
- 纯电阻
- RC
- RL
- RLC
- 独立电压源
- 独立电流源
- 受控源
- 运放
- 二极管
- BJT
- MOSFET
- 开关

异常：
- 缺节点
- 未知元件
- 端口不完整
- 重复 id
- 孤立元件
- 无 ground
- critical uncertainty
- 非法 net

必须验证：
合法 IR → rendered/degraded
非法 IR → invalid + ValidationIssue
Renderer fail → 稳定 failed result，不抛裸异常。

现阶段只使用现有 renderer / SchemDraw / deterministic fallback，不引入 ngspice 等。

输出：
`docs/audit/50_circuit_standalone_report.md`

提交：
`test(circuit): harden circuit rendering baseline`
