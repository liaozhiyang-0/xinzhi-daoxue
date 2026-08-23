# M3：Backend Application + Capability Consolidation

## Application
把 use-case coordination 逐步归入：
```text
application/tasks/
application/chat/
application/sessions/
application/learning/
```
只负责协调、适配、commit/session 流，不承载专业计算。

## Capability
建立：
```text
capabilities/academic_solver/
capabilities/knowledge/
capabilities/teaching/
capabilities/research/
capabilities/learning/
capabilities/general/
```

### Academic Solver
保留稳定 facade：`AcademicProblemSolverService`。
内部按实际职责拆：
normalization / classification / strategy / execution / verification adapter / result building / course adapters。

禁止重新按课程建立多个 public Solver。

## Compatibility
移动模块允许旧 path 临时 re-export：
```python
from app.capabilities.xxx import XxxService
```
必须标记 deprecated compatibility import，最终只保留单实现。

## Internal Agent
`internal_agent_execution.py` 只保留内部 Worker 调度/调用，专业业务逻辑移回 capability。

每移动一组都做 import、targeted test、dependency DAG、runtime path test。
本阶段不 commit。
