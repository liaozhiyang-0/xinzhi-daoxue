# 04 产品方案

当前可核验的工程边界：

- FastAPI + SQLAlchemy + Alembic 任务服务，任务创建与 Provider 执行分离。
- CT/AE/DE/SS 等课程包由统一 Course Registry 管理，课程规则不复制 Solver 实现。
- 文本、图片、PDF、DOCX 解析与本地知识库检索保留 provenance、checksum 和质量问题记录。
- 教学闭环包含学生尝试、验证、提示、首错定位、反馈采纳和教师统计入口。
- 评测提供离线案例校验、摘要报告和元数据可观测性；不把离线结果宣称为学习效果。

建议引用：

- `docs/audits/challenge_cup_phase1_audit.md`
- `docs/implementation/p1_document_quality.md`
- `docs/implementation/p2_learning_metrics.md`
- `docs/implementation/p3_evaluation_observability.md`
- `docs/implementation/p4_course_asset_audit.md`
