# P38：任务终态附件清理与超时竞态

## 背景

P37 的评测 runner 会在任务查询到终态后清理附件，但外层评测超时可能先取消轮询，而后台任务仍在读取附件。反过来，任务状态先提交为终态、清理后执行时又可能遇到应用生命周期关闭，产生残留。

## 实现

- 新增 `cleanup_evaluation_attachments` 服务，统一按精确文件 ID 或任务 ID 清理，并强制要求 `purpose == "evaluation_attachment"`。
- 任务成功、失败、取消，以及排队任务直接取消时，在终态事务提交前清理附件；清理使用嵌套事务，清理异常不会回滚任务终态。
- 路由未选中导致任务创建阶段直接失败时，同样清理已绑定的评测附件。
- 评测 runner 只有在任务尚未创建时清理附件；任务已创建但评测超时/取消时保留附件，交由任务真正进入终态的路径清理，避免后台读取竞态。
- 非评测附件、课程资料、学生上传文件不参与此清理。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_evaluation_framework.py `
  apps/api/tests/test_task_cancel.py -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests scripts
.\.venv\Scripts\python.exe -m mypy apps/api/app
```

新增回归覆盖：

1. 评测任务仍在 `queued` 时被取消，附件记录和本地对象均删除。
2. 评测 runner 被取消时，不提前删除仍处于非终态任务的附件。
3. 本地 `/files → /tasks → 后台任务 → 终态` 链路完成后，附件被清理且无竞态残留。

## 风险与边界

- 评测附件是一次性受控输入，任务失败后不保留供 retry 使用；需要重试时应重新上传并重新创建评测任务。
- 未执行真实 Provider、真实 OCR 或 Docker；本阶段不修改冻结 `SOLVER_CT v1.0/SOLVER_CT_V1`，也不纳入三个演示案例。
- 后续可增加残留附件巡检指标和进程异常退出后的定期回收任务。
