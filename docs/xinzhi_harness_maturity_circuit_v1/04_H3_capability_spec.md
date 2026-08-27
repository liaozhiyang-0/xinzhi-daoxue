# H3：CapabilitySpec Metadata 增强

目标：增强 Capability 可描述性，不改变执行语义。

在现有 BaseCapability 基础上增加描述型 metadata：

CapabilitySpec:
- capability_id
- input_modalities
- output_types
- tool_ids
- side_effect
- idempotent
- cacheable
- cost_class
- latency_class
- requires_network
- requires_approval
- artifact_types
- provider_requirements

旧 Capability 未声明时必须安全默认。

Circuit 示例：
capability_id = circuit.render
input_modalities = [circuit_ir]
output_types = [circuit_svg]
side_effect = false
idempotent = true
cacheable = true
cost_class = low
latency_class = low
requires_network = false
requires_approval = false
artifact_types = [image/svg+xml]

H3 阶段 Planner 不根据 metadata 改计划，只允许 registry/debug/readiness/evaluation 读取。

验收：所有现有 Capability 行为与 H2 一致。

提交：
`refactor(capability): add descriptive capability specs`

输出：
`docs/audit/49_capability_spec_report.md`
