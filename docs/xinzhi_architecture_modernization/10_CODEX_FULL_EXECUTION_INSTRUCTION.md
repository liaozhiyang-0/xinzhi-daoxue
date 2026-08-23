# Codex Phase M 全量执行指令

执行“芯智导学 Phase M：Frontend + Backend Architecture Modernization”。

用户已暂停 T0-T9 Benchmark。

严格按：
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9。

## 约束
1. 目标是工程现代化，不增加 Agent 功能。
2. 前端迁移 React + TypeScript + Vite。
3. 后端收敛 services，建立 application / capabilities / runtime / infrastructure / governance。
4. 不新增 public Agent。
5. 不创建第二 Runtime。
6. 不改变 Planner/Skill/Reflection/Experience/Evaluation owner。
7. 不改变 Task API、Chat API、SSE、Task lifecycle、checkpoint/resume 业务语义。
8. 不修改真实测试题 expected answer。
9. 不以减少 LOC 为目标。
10. 不把专业业务逻辑塞入 Runtime。
11. 不把后端业务逻辑复制到 React。
12. generated OpenAPI TS types 保持唯一 contract source。
13. React 第一版不默认引入 Redux/Next/TanStack/Tailwind 等额外复杂度。
14. M0-M8 不 commit/push。
15. M9 才统一一次大阶段 commit/push/CI。
16. 禁止 force push / reset --hard / clean -fd。
17. 不自动 merge main。

## 允许自主调整
具体目录、模块命名、组件/hook 边界、compatibility facade 数量、move order、test selection可按实际调整，但总体方向不能变。

## 后端兼容迁移
```text
new canonical module
+ temporary old-path re-export
+ migrate imports
+ tests
+ zero importer 后移除 facade
```
不得复制实现。

## 前端兼容迁移
```text
React alternate entry
+ feature-by-feature parity
+ default switch
+ parity 后移除 legacy
```

## 每阶段
inspect → change → targeted validate → write local audit → continue，不提交。

## 停止条件
- destructive DB migration
- unavoidable breaking public API
- second Runtime path
- task/SSE/resume 无法维持 parity
- unrelated dirty changes 无法安全隔离
- critical regression 两轮最小修复仍失败

## 最终
M9 生成 `docs/modernization/phase_m_closeout.md`，统一 commit/push/CI。
完成后不要自动执行 T0-T9，只写明 ready to resume T0 并停止。
