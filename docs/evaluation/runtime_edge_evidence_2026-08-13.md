# Runtime / Edge 补充验证记录（2026-08-13）

本记录补充 2026-08-12 Edge 记录，不代表所有业务路径或发布门禁已完成。

## 路由问题根因与修复

Edge 首次复测发现请求“请将‘实验说明滤波器效果很好’改写为严谨学术表达；没有提供实验数据”被路由到“数据分析”，页面显示“该工作流尚未发布”。根因在 `IntentRecognitionService._match()`：写作词和数据词同时出现时，无条件采用“先分析后写作”规则，没有区分“没有提供实验数据”这一否定式边界说明。

修复位于 `apps/api/app/services/intent_recognition.py`：只有不存在否定式数据表达时，才保留 data-analysis-first 规则；否定式数据说明保留 `academic_writing`。新增测试覆盖该句，同时保留真正“先分析实验数据，然后写成论文段落”的 data-analysis pipeline 测试。

## 最新 Edge 复测

- 只启动一个 API，端口 `8000`；`TASK_EXECUTOR_MODE=local`，没有独立 Worker。
- 最新代码重新启动后，`/api/v1/health` 返回 `status=ok`，database/redis/minio 均为 `ok`。
- 同一句请求进入学术写作 Runtime 的人工审批 checkpoint，不再进入“数据分析/该工作流尚未发布”。
- Edge 页面显示长等待提示和“等待人工审批”，没有伪造资料依据。
- 无授权审阅者条件下点击停止，页面显示“任务已停止/未生成新结果”，没有把空结果当作完成。

## 测试与发布边界

- 意图识别和路由回归：`52 passed`。
- 之前已完成的证据归一化、外部链接、刷新/重连、取消、暂停/恢复等 Edge 证据仍以 2026-08-12 记录为准。
- 审批后恢复仍需要授权审阅者账号；本地游客会话未绕过权限。
- 文件上传仍受 Edge 控制层本地文件注入权限限制，错误为 `Not allowed`，没有伪造上传成功。
- Runtime release preflight 继续 fail-closed；没有新增 canary/default 授权，也没有进入 RESEARCH_03 迁移或审计。
