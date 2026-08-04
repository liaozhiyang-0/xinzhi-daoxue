# P7 显式用户反馈与运营统计

## 现状边界

`feedback_uptake` 是“学生修改答案后，系统判断提示是否被采纳”的学习遥测，不是用户满意度或问题反馈。P7 增加独立的 `task_feedback` 记录，避免把行为推断写成用户评价。

## 数据与接口

- `POST /api/v1/feedback`：任务完成、失败或取消后提交或更新一条任务反馈。
- `GET /api/v1/feedback/metrics`：教师/管理员查看时间窗口和课程范围内的聚合统计。
- 工作台在回答区提供是否解决、满意度、问题类型、人工复核请求和可选备注。

反馈保存时同步记录任务上下文快照：用户角色、课程、任务类型、Agent/Provider、Agent 版本、模型标识或版本、RAG/index 版本、检索模式、引用覆盖率和延迟。若运行链路没有提供某个版本或指标，字段保持 `null`，不推断或补造数值。

## 隐私与权限

- 反馈回显不返回 `user_id`；管理统计只返回计数、比例和聚合字段。
- 认证开启时，提交者只能反馈自己的任务；统计仅 teacher/admin 可读。
- 备注长度受限，并提示不要填写敏感个人信息。
- 统计输出明确标注为本地运营遥测，不等同于准确率、学习效果或正式成绩。

## 可复现验证

```powershell
cd C:\Users\86184\Desktop\xinzhi-daoxue
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_feedback_api.py -q
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_student_web.py -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

当前阶段未执行真实 Provider、真实用户试用或 Docker；回归使用本地数据库和 Mock 配置。三个演示案例仍由项目方自行设计。
