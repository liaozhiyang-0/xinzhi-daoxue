# T9：Final Acceptance Benchmark

## 目标
形成用于挑战杯答辩、项目验收、Demo、Release Candidate 的正式测试结果。

## 必须运行
Regression Suite、Hidden Holdout、Targeted Suites、Robustness Suite、336 original benchmark、Expanded Benchmark。
真实 Provider subset 按预算执行。

## 最终指标
Quality：overall/course/difficulty/hard/image/formula/knowledge/research/teaching。
Architecture：planner/skill/rag/tool/reflection/experience/verification。
Stability：runtime failure/fallback/resume/retry/timeout。
Performance：p50/p95/tokens/cost。

## 最终 Before / After
至少输出 Benchmark V1 vs Benchmark Final。

## Release Gate
critical regression = 0；hidden holdout acceptable；public API compatible；runtime stable；CI status known；benchmark reproducible；known limitations documented。

## 提交
`release: finalize benchmark and acceptance results`
