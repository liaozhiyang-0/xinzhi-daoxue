# P59：最终风险清单与可复现验收入口

P59 将当前阶段的工程状态、未决外部输入和验收命令集中记录，便于负责人休息后继续维护。本文不是竞赛成绩、官方规则核验、真实用户试用或线上部署证明。

## 当前已确认状态

- CT/AE 课程资产均保持 `runtime_loaded=false`，候选错误模板均未进入运行时。
- CT 有 4 条候选、AE 有 6 条候选；确定性结构化校验证据分别为 4/4 和 6/6，但教师材料证据仍待补齐。
- 竞赛材料包状态为 `draft_evidence_only`，10 个声明文件均存在，证据矩阵非空且没有缺失文件。
- 官方规则、官方成绩声明、三个演示案例、真实用户结果和真实 Provider 结果均保持禁止/未声明边界。
- 当前没有 `config/error_pool/releases/` 下的有效 release 文件；本阶段没有执行 Docker、Provider 或 OCR。

## 未决风险与责任边界

1. `01_participation_info.md` 仍等待官方规则和提交格式；不能据此推断竞赛要求。
2. `03_demo_user_guide.md` 中的三个演示案例由项目负责人自行设计；本阶段不代写、不生成、不纳入测试结论。
3. `08_user_pilot_log.md` 仍等待授权试用记录；本地评估不能替代真实用户结果。
4. `05_source_and_model_notes.md` 仍等待 release inventory；候选错误模板必须完成教师审核和证据追踪后才可讨论发布。
5. `10_deployment_and_operations.md` 仍等待 Docker 与政策记录；Docker 未执行，不能声称完成部署验收。
6. 知识库当前仍有质量问题记录，CT/AE OCR 元数据状态为 `unavailable`；任何 OCR 重建或外部材料补录都应单独授权并保留来源。

## 推荐验收顺序

在 Windows PowerShell 中，从项目根目录执行：

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy apps/api/app
.venv\Scripts\python.exe scripts/check_sensitive_files.py
.venv\Scripts\python.exe scripts/validate_config.py
.venv\Scripts\python.exe scripts/export_openapi.py
.venv\Scripts\python.exe scripts/run_evaluation.py --validate-only
.venv\Scripts\python.exe scripts/audit_course_assets.py --course CT --course AE
.venv\Scripts\python.exe scripts/audit_readiness_consistency.py --course CT --course AE
.venv\Scripts\python.exe -m pytest apps/api/tests -q --no-cov
node --check apps/api/app/static/debug/teacher.js
git diff --check
```

关键检查点：配置 `valid=true`；validate-only 的 `sends_api_requests=false`；资产审计无 schema 或边界错误；一致性审计 `status=consistent`；候选模板的运行时可用数量为 0。若要执行真实 Provider、OCR、Docker 或录入试用结果，必须先补齐授权、来源和审计记录。
