# P21：课程资产与竞赛支撑 readiness 摘要

## 目标

把 CT/AE 课程资产清单、错误模板教师复核队列和竞赛材料包的证据边界统一成一个只读 readiness 摘要，明确“已实现”“部分完成”和“仍需外部/负责人输入”的区别。

## 实现

- 新增 `course_asset_readiness.v1` 服务与契约；
- 新增 `GET /api/v1/knowledge/course-asset-readiness?course_id=CT|AE`；
- readiness 输出包括：课程包状态、运行时加载边界、资产 readiness 项、来源文件状态、错误模板复核队列计数、阻塞项、下一步动作和竞赛包边界；
- 教师工作台增加 `Course Asset Readiness` 只读卡片；默认显示 CT/AE，DE 显示适用范围提示；
- 官方规则、真实用户结果、三个演示案例和教师证据缺失时只标为 pending/blocker，不自动补写或宣称完成。

## 运行与验证

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
node --check apps/api/app/static/debug/teacher.js
```

浏览器验收覆盖默认 CT/AE 聚合、CT/AE 切换、DE 边界、readiness 阻塞项、运行时边界和控制台错误检查。

## 当前风险

当前 CT/AE readiness 为 `evidence_pending`：错误模板分别有 4/6 项待教师复核，官方规则、真实用户结果和负责人设计的三个演示案例仍未提供。该摘要是工程状态报告，不是官方竞赛验收或成绩证明；本阶段没有真实 Provider 调用，也没有修改冻结 `SOLVER_CT_V1`。
