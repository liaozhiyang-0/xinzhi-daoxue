# P22：Readiness 证据一致性检查

## 目标

避免课程资产 readiness 仅依赖 YAML 中的状态声明。P22 为每个 readiness 项增加可复核的 `evidence_checks`，区分工程实现证据、部分覆盖和竞赛外部证据边界。

## 状态语义

- `present`：声明对应的迁移、API、服务或测试文件存在；
- `partial`：工程能力存在，但覆盖范围仍不完整，例如 CT/AE 错误模板覆盖；
- `boundary_declared`：仓库明确记录了边界，但这不是官方规则、真实用户结果或负责人案例的证明；
- `observed_status`：根据当前文件和运行时配置观察到的状态；
- `readiness_evidence_mismatch_*`：仅当声明为 `implemented` 而实际观察不到实现时生成阻塞项。

## 变更

- `course_asset_readiness.v1` 增加 `evidence_checks`；
- 校验材料生命周期、教师复核门禁、反馈统计、错误模板覆盖和竞赛边界文件；
- 教师工作台 readiness 卡片显示 `evidence_status` 与 `observed_status`；
- 不一致或证据文件缺失会生成阻塞项和下一步动作；
- 不会自动批准错误模板、验证官方规则、生成演示案例或写入真实用户结果。

## 验证

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
node --check apps/api/app/static/debug/teacher.js
```

浏览器验收确认 CT/AE 两张卡片显示 `present/partial/boundary_declared` 证据状态，当前没有 readiness evidence mismatch，控制台无错误或警告。

## 剩余缺口

官方规则原文、授权用户试用记录、真实结果和三个演示案例仍需要项目负责人或授权来源提供；当前 readiness 继续保持 `evidence_pending`，不能作为竞赛成绩或官方验收结论。
