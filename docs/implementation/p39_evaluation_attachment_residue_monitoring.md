# P39：评测附件残留监控与受控回收

## 目标

P38 将正常任务路径的评测附件清理收口到任务终态之前，但进程异常退出、数据库提交中断或存储删除异常仍可能留下受控附件记录。P39 增加只读巡检和显式执行的批量回收入口，继续把影响范围限制在 `purpose == evaluation_attachment`。

## 实现

- `evaluation_attachment_maintenance.py` 提供残留统计和候选筛选，不修改数据库或存储。
- 管理端新增 `GET /api/v1/admin/evaluation-attachment-residue`，仅管理员可访问。
- 候选必须同时满足：超过 `EVALUATION_ATTACHMENT_CLEANUP_GRACE_SECONDS` 宽限期，且未绑定任务、绑定任务已进入 `completed/failed/cancelled`，或任务记录缺失。
- `running`、`queued`、`created`、`waiting_user`、`waiting_review` 等非终态任务的附件永远不会进入候选。
- `scripts/maintain_evaluation_attachments.py` 默认只读；只有显式传入 `--execute` 才会删除一个有上限的候选批次，默认最多 100 个文件。
- 回收仍复用 P38 的精确文件 ID 白名单和 `evaluation_attachment` purpose 校验，不触碰课程资料、学生上传或通用文件。

## 配置

```dotenv
EVALUATION_ATTACHMENT_CLEANUP_GRACE_SECONDS=86400
```

宽限期默认 24 小时，可配置范围为 60 秒至 30 天。正式环境应结合任务最长执行时间和故障排查窗口设置，不建议直接设置为 0。

## 使用与验证

只读巡检：

```powershell
.\.venv\Scripts\python.exe scripts/maintain_evaluation_attachments.py
```

确认报告中的 `cleanup_candidate_count` 后，再执行有界回收：

```powershell
.\.venv\Scripts\python.exe scripts/maintain_evaluation_attachments.py --execute --limit 100
```

API 回归测试：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_admin_management.py -q
```

## 边界与风险

- 本阶段不扫描或删除对象存储中没有数据库记录的未知对象；避免凭路径猜测删除用户数据。若后续需要处理这类对象，必须先增加存储端列举能力、前缀白名单和二次确认机制。
- `--execute` 不会自动启动，也不由应用请求路径触发；需要运维人员明确执行。
- 本阶段没有真实 Provider、OCR、MinIO 或 Docker 调用，也没有修改数据库结构或冻结的 `SOLVER_CT v1.0/SOLVER_CT_V1`。
- 三个演示案例不纳入本阶段自动化。
