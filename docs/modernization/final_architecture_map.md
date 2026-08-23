# Phase M Final Architecture Map

```text
React Workspace (/workspace)
  ├─ features / components / hooks
  └─ typed API boundary
       ↓
FastAPI API / SSE
       ↓
application use cases
  └─ task query/progress/coordinator + session/task boundary
       ↓
capability contracts
  ├─ Academic Solver
  ├─ Knowledge / RAG
  ├─ Teaching / Learning
  ├─ Research
  └─ General
       ↓
single RuntimeTaskEngine
  ├─ plan / lifecycle / checkpoint / recovery / event semantics
  └─ capability handler ports
       ↓
infrastructure adapters
  ├─ model/provider
  ├─ RAG/vector/storage
  └─ tool/internal-agent composition
       ↘ governance
          verification / reflection / experience / evaluation
```

## Invariants

1. React does not execute domain logic or call providers directly.
2. There is one Task API contract, one RuntimeTaskEngine and one SSE protocol.
3. Compatibility facades do not contain duplicate implementations.
4. Academic Solver remains the stable public professional solver facade.
5. Planner, Skill, Reflection, Experience and Evaluation owners remain in their existing canonical locations.
