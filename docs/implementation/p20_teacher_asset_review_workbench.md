# P20：教师工作台课程错误模板复核队列

## 目标

将 P19 的 CT/AE 错误模板候选清单接入教师工作台，只提供可追溯的只读查看，不提供自动批准、发布或运行时加载能力。

## 变更

- 新增 `course_asset_review` 服务，从课程技能、已审核错误池、候选 proposal 和教师复核记录构建 `teacher_review_queue.v1`；
- 新增 `GET /api/v1/knowledge/course-asset-review-queue?course_id=CT|AE`，仅允许教师/管理员（开发环境游客模式可读），不写数据库、不调用 Provider；
- 教师工作台默认聚合 CT/AE，选择 CT/AE 时显示对应队列，选择 DE 时显示适用范围提示；
- 每项展示错误签名、proposal、关联技能/题型、P1/P2 优先级、复核决定、证据引用和 `Runtime excluded` 状态；
- 接口和前端均不包含批准按钮，候选项始终 `runtime_eligible=false`。

## 运行与验证

启动本地 Mock API 后访问 `/teacher`，或直接调用：

```powershell
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
```

相关检查：

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
node --check apps/api/app/static/debug/teacher.js
```

浏览器验收覆盖默认 CT/AE 聚合、CT/AE 切换、DE 边界、只读内容和控制台错误检查。

## 风险与边界

当前 CT 4 项、AE 6 项仍处于 `pending_teacher_review`，没有真实教师证据，因此不能 promotion；官方竞赛规则、真实用户结果和三个演示案例仍保持未验证/由项目负责人设计。
