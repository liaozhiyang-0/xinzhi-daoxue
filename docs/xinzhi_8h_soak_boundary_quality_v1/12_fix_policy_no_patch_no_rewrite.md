# 12 问题修复政策：不补丁、不重写主线

所有问题先分类：
UX
LATEX
PRESENTATION
SEMANTIC
ROUTER_HINT
CONTEXT
MULTIMODAL
RAG
PROVIDER
TOOL
CIRCUIT_IR
CIRCUIT_VALIDATION
CIRCUIT_RENDER
ARTIFACT
SSE
QUEUE
RESOURCE

先聚类，再找共享根因。

例如 10 个公式失败若都源于 Markdown normalization，只修统一规范化层，不给 10 个 case 加特判。

除非有明确系统性缺陷并提交独立架构变更提案，否则禁止修改：
Planner owner
Runtime owner
CanonicalPlan ownership
TaskExecutionCoordinator architecture
ProductionExecutionManifest
Memory major architecture

优先允许修：
shared presentation
normalizer
validator
capability adapter
tool guard
circuit validator/layout
provider policy
RAG postprocess
ContextAssembly 局部共享逻辑

每次修复：
failure cluster
→ reproduction
→ root cause
→ impact analysis
→ smallest shared fix
→ target test
→ golden baseline
→ browser
→ continue soak

如果根因确实要求改主线：STOP，输出 architecture-change-proposal，不直接动。

所有修复记录：
`docs/audit/78_soak_fix_log.md`
