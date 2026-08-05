# P3 评测与可观测性边界

## 目标

为教师和管理端提供可复现、低暴露面的评测摘要，同时保留本地原始报告用于审计。三个演示案例不在本阶段自动设计或改写。

## 新增接口

- `GET /api/v1/evaluation/reports/latest/summary`
  - 受 `ENABLE_EVALUATION_API` 控制。
  - 开启认证时仅教师和管理员可访问。
  - 只返回汇总、统计、状态计数和运行元数据，不返回 `results`、答案、提示词或推理内容。
- `GET /api/v1/evaluation/observability/model-calls`
  - 返回当前进程内模型调用的数量、状态、Provider、模型、任务类型和耗时聚合。
  - 仅使用有界内存中的元数据，不保存提示词、图片或推理内容。
  - 开启认证时仅教师和管理员可访问。

`GET /api/v1/evaluation/reports/latest` 仍保留给本地审计使用；`evaluation/reports/latest.json` 可能包含案例级答案和任务细节，不应直接用于教师工作台或对外接口。

## 可复现元数据

新生成的 `SuiteReport` 增加 `run_metadata`：

- `run_id`：本次运行标识。
- `case_count`：实际执行案例数。
- `case_ids_sha256`：案例 ID 集合的 SHA-256 指纹。
- `implementation_fingerprint`：评测实现与相关配置的缓存指纹。
- `execution_channel`：当前为进程内 HTTP 调用链。
- `model_trace_retention`：有界内存、仅元数据。
- `raw_prompts_stored`：固定为 `false`。

旧报告缺少 `run_metadata` 时，会使用兼容默认值解析；这不为旧报告补造指纹。

## 运行与验证

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\pytest.exe apps/api/tests/test_evaluation_api.py apps/api/tests/test_evaluation_framework.py -q
.\.venv\Scripts\ruff.exe check apps/api/app
.\.venv\Scripts\mypy.exe apps/api/app
```

上述校验不会执行真实 Provider 调用。离线、Mock 或本地确定性评测结果也不能表述为真实学习效果或竞赛成绩。
