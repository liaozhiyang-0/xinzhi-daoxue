# 芯智导学：8+ 小时持续稳定性、边界能力与浏览器质量验收 v1

前置条件：Production Execution Surface 已锁定；Legacy 可执行路径已隔离；当前稳定版本已有明确 Stable Baseline；Circuit Rendering v1 已完成接入。

本阶段不是新功能开发，而是至少 8 小时的真实长期、重复、混合、浏览器驱动测试。

核心目标：
- 长时间运行后唯一生产链不漂移；
- 浏览器最终答案观感可靠；
- LaTeX/KaTeX 在复杂电子信息公式中稳定；
- CT/AE/DE/SS、六案例、RAG、多图、长对话和 Circuit 均有专项测试；
- 后端统计 p50/p95/p99、资源增长和各阶段耗时；
- 发现问题后修共享根因，不改主框架主线，不做 case-specific 补丁。

硬规则：
1. 总测试持续时间 >= 8h，推荐 10~12h。
2. Browser First + Backend Metrics。
3. 禁止重写 Unified Ingress / Planner owner / CanonicalPlan owner / TaskExecutionCoordinator / RuntimeTaskEngine / ProductionExecutionManifest。
4. 禁止通过清 DB/Redis、删测试、降评分、统一延长 timeout 伪造稳定。
5. 每个问题必须：Failure → Cluster → Shared Root Cause → Smallest Shared Fix → Regression → Browser → Continue Soak。
6. Circuit Renderer/Artifact 失败不能拖垮 Solver。
7. Legacy executable counters 全程必须保持 0。

最终输出 `docs/audit/68` 到 `80` 系列报告。
