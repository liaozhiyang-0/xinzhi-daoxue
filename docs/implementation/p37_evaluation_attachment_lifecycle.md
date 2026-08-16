# P37：评测附件本地任务链与生命周期

## 目标

在不把三个演示案例纳入自动设计的前提下，补齐受控评测附件从本地文件到任务执行的离线闭环，并避免评测运行在本地数据库和对象存储中留下临时文件。

## 已完成

- `EvaluationRunner` 先通过本地 `/api/v1/files` 上传受控案例文件，再把返回的安全 `AttachmentRef` 传给 `/api/v1/tasks`。
- 评测任务保持非阻塞：创建任务后轮询现有任务查询接口直到终态。
- 仅清理本次运行自己上传、且 `purpose == "evaluation_attachment"` 的文件；清理按本次上传返回的文件 ID 白名单执行，不扫描或删除用户文件、课程资料或其他评测运行的文件。
- 清理放在任务终态之后；创建会话、任务或后续动作失败时也会进入清理路径。
- 文件上传后若文本/PDF 摄取处于 `pending`、`processing` 或 `failed`，评测不会把它当作可执行附件；已经上传的文件仍会按 ID 回收。PDF OCR 继续停留在人工复核边界，不自动调用或批准 OCR。

## 验证

在 PowerShell 中执行：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app/evaluation/runner.py apps/api/tests/test_evaluation_framework.py
```

新增集成回归会生成一个有效 PNG，走真实的应用内 `/files`、`/sessions`、`/tasks` 和后台任务轮询链，并检查终态后附件记录与本地存储对象均已删除。该测试使用项目 Mock/离线配置，不代表真实模型调用结果。

## 边界与后续

- 评测报告仍只保存案例清单、哈希和结果摘要，不保存原始本地路径。
- 真实 Provider、真实 OCR、学生隐私资料和三个演示案例仍不在本阶段自动化范围内。
- 下一步可在不改变清理白名单原则的前提下，补充任务取消/超时后的附件回收测试，并继续检查长期运行时的残留文件监控。
