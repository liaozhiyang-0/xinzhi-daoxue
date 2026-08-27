# Codex 总执行指令：8+ 小时持续稳定性与边界验收

读取并严格执行本目录全部文档。

本阶段不是新功能开发。

目标：对当前稳定版本进行至少 8 小时真实长期、重复、混合、浏览器驱动稳定性和边界测试，并对问题做共享根因修复。

## 不动主线
禁止重新设计 Unified Ingress、GoalContract、Planner ownership、CanonicalPlan ownership、TaskExecutionCoordinator、RuntimeTaskEngine、ProductionExecutionManifest、Memory major architecture。

若问题必须改这些层才能解决：
STOP + 输出 architecture change proposal。

## 浏览器强制
必须反复使用：
http://127.0.0.1:8000/workspace

重点检查：
回答观感、Markdown、LaTeX/KaTeX、表格、资料卡片、多图、Circuit SVG/Artifact、loading/error/review、refresh/history。

## 后端耗时和资源
统计 p50/p90/p95/p99/max。
尽量拆 planning/RAG/vision/model/tool/verification/circuit/artifact/presentation。

监控：
API RSS、DB connections、Redis、Qdrant、MinIO、running tasks、lease、execution fingerprint、legacy counters。

## 至少 8 小时
不能用快速 mock 冒充。推荐 10~12h。
必须有较长连续运行窗口观察 drift。

## 必测专项
六业务案例
CT/AE/DE/SS
General
RAG
单图/多图
长对话
Session isolation
same-question repeatability
restart/recovery
Provider failure
SSE reconnect
LaTeX
Circuit Drawing
Circuit AUTO
Circuit Artifact

## Circuit
重点不是图生成成功，而是元件、参数、节点、支路、极性、拓扑和可读性。
Renderer/Artifact 失败不得影响 Solver。

## LaTeX
构建 50~100 条电子信息真实复杂公式 fixture，并在浏览器实际验证。错误公式只能局部降级。

## 修复政策
Observed Failure
→ Cluster
→ Shared Root Cause
→ Impact Analysis
→ Smallest Shared Fix
→ Target Test
→ Golden Regression
→ Browser Validation
→ Continue Soak

禁止 case-specific if、prompt hardcode、降低评分、删测试、清数据库、统一无限增加 timeout、重写框架。

## 每次修复后
运行 target tests + golden baseline + affected browser cases。
影响 Circuit 时必须跑 OFF/ON/AUTO。
影响公式时跑完整 LaTeX fixture。

## 报告
生成：
68_soak_test_baseline
69_browser_visual_quality_report
70_latex_katex_torture_report
71_backend_latency_resource_report
72_six_scenario_targeted_report
73_circuit_stress_report
74_multimodal_boundary_report
75_long_context_session_report
76_restart_failure_recovery_report
77_repeatability_report
78_soak_fix_log
79_8h_soak_final_report
80_long_run_stable_baseline

## 通过条件
只有 soak>=8h + browser final matrix + legacy counters=0 + execution drift=0 + Circuit OFF regression=0 + critical LaTeX failure=0 + session leakage=0，才允许标记 LONG_RUN_STABLE。

最终返回：
HEAD、commits、test duration、task counts、browser counts、p50/p95/p99、resource trend、LaTeX quality、Circuit quality、六案例质量、repeatability、restart results、all fixes、remaining risks、git status。

最终目标不是“跑完8小时”，而是证明芯智导学在真实浏览器、真实模型、多模态、Circuit、长对话和持久状态共同存在时，长期反复使用仍保持唯一执行链、稳定答案质量、可靠公式渲染、可接受耗时和清晰产品体验。
