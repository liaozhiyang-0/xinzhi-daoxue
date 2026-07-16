# 本地阶段 0—1.5 实施范围

本阶段冻结 `SOLVER_CT_电路理论专业解题_v1.0` 的公开基线，并建设 FastAPI、数据库、Mock Provider、任务生命周期、SSE、文件与产物闭环。

当前明确边界：

- `SOLVER_CT` 尚未发布外部 API。
- 不实现或猜测星辰鉴权、运行、流式、取消和状态接口。
- 本地使用明确标记的 Mock Provider。
- 任务创建非阻塞，后台使用独立数据库 Session。
- 不引入 Celery、LangGraph、Kubernetes 或复杂正式前端。
- 原始星辰 YAML 只允许存在于被 Git 忽略的 `.local_inputs/`。

进程内 TaskRunner 是阶段性实现。API 进程重启可能中断正在运行的任务，后续可由独立 Worker 替换。
