# M4：Runtime / Infrastructure / Governance Consolidation

## Runtime 只负责
execution / lifecycle / checkpoint / resume / retry / cancel / timeout / fallback / event / handler invocation / runtime policies。

禁止迁入 KCL/KVL、RAG domain logic、教学设计、科研综合、学情诊断。

## Infrastructure
逐步归入：
providers / rag / storage / database / external。

依赖方向：
```text
Capability → interface → infrastructure implementation
```

## Governance
归入：
verification / reflection / experience / evaluation。

保持：
- verification = 硬门禁
- reflection = bounded internal critic
- experience = bounded planner prior
- evaluation = quality evidence owner，不拥有 Task lifecycle

## services
目标不是清空。允许保留 compatibility facade、真正 cross-cutting service、暂缓高风险模块。

结构检查：
- dependency DAG
- single RuntimeTaskEngine
- no capability → API reverse dependency
- runtime 不 import 课程具体实现
- planner 不 import concrete provider
- governance 不拥有 task lifecycle

本阶段不 commit。
