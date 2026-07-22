# Stage 2.2 Agent Registry Review

## 评审结论

Stage 2.2 已在现有分支完成统一场景注册、确定性路由、受控降级、通用星辰工作流调用、输入能力校验、非敏感状态接口和调试页可观测字段。未新增仓库、分支、PR、工作树、数据库迁移或第二套运行链路。

## 注册与运行边界

- dispatch 与 learning 场景已启用；teaching、research、infrastructure 为 planned。
- `SOLVER_CT_V1` 保持 enabled/published，并继续使用真实文字与单图片星辰调用。
- 云端学习问答、答案检查、云端兜底路由、教学和科研 Agent 已注册但保持 planned/disabled。
- 本地学习检索已命名为 `LEARN_01_LOCAL_RETRIEVAL_V1`，作为云端学习 Agent 的显式 fallback。

## 安全与一致性检查

- Flow、Key、Secret 未写入 YAML、代码、状态接口或文档。
- Provider 根据注册表映射构造请求，不存在 Agent 专用 HTTP 分支。
- 未支持输入会明确失败，不静默丢弃附件。
- 云端调度目标必须通过注册、启用、非自身、课程、输入和运行可用性校验；无效目标返回 `route_invalid_target`。
- 所有调度元数据复用 Task input/result/event JSON，无迁移。

## 验证范围

覆盖注册表与 Flow 解析、Solver 路由、学习问答降级、答案检查降级、AE/DE 不误入 CT Solver、云调度非法目标、配置缺失、PDF/多附件拒绝、状态接口和统一任务执行。运行命令：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app apps/api/tests
.\.venv\Scripts\python.exe -m mypy apps/api/app
python scripts/validate_config.py
git diff --check
```

真实云端调用仍只对本机 `.env` 中已启用、已发布且 Flow 配置完整的 Agent 开放；计划态工作流需在星辰侧发布并配置对应 Flow 后再启用。
