# M7：Cross-stack Parity 与 Regression

## 前端 parity
旧 Workspace vs React：
session、submit、SSE、message、Markdown、LaTeX、citation、source、artifact、attachment、learning、cancel、retry、resume、fallback、error、debug。

## API
OpenAPI stable/additive only；generated TS types reproducible；contract drift PASS。

## 后端 parity
Task API、Chat adapter、Task lifecycle、SSE order、checkpoint/resume、planner、skill binding、reflection、experience、evaluation、RAG/tool interfaces。

## 测试
Backend：
- relevant unit/contract
- runtime path
- API integration
- planner/skill/reflection/experience regression
- dependency constraints
- full pytest if reasonably executable

Frontend：
- typecheck
- build
- smoke
- API contract check
- React workflow smoke

如已有 E2E harness，加入 submit→stream→complete、attachment→answer、learning、retry/resume。

## Critical Gate
出现 task 无法完成、SSE 顺序变化、session 丢失、contract mismatch、resume 变化、第二执行路径等必须修复后才进入 M8。

本阶段不 commit。
