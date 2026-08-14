# Runtime / Edge 应用验证记录（2026-08-12）

本记录只证明本地开发环境中的前后端应用流程和资料依据呈现，不构成
Runtime 语义等价证明、生产 canary、默认发布或人工发布决定。测试过程中只
启动一个 API 实例；`TASK_EXECUTOR_MODE=local`，没有启动独立 Worker。

## 资料依据异常

### 根因

Runtime 恢复或校验路径可能只保留 `external_retrieval.items`，而前端优先读取
`external_search_view`。JavaScript 中空数组为 truthy，导致空的 view 不会回退到
retrieval items。回退对象使用 `canonical_url` 和 `content_excerpt`，原卡片只读取
`url` 和 `abstract`，因此可能出现没有可点击来源链接或没有摘要的证据卡片。

### 修复

- 统一从 `external_search_view` 或非空的 `external_retrieval.items` 读取外部证据。
- 支持 `url`、`canonical_url`、`source_ref`、DOI 和 arXiv ID 的安全链接归一化。
- 支持 `abstract`、`content_excerpt` 和 `excerpt` 的摘要归一化。
- 按 evidence ID、URL、DOI、arXiv ID 或标题去重。
- 前端构建标识递增到 `20260812-workspace-math-recovery-v23`，避免 Edge 使用旧资源。

## Edge 实际观察

| 场景 | 实际表现 | 结论 |
| --- | --- | --- |
| 学术检索 | 返回 2 张唯一外部证据卡片，标题、摘要、日期、来源类型和 arXiv ID 对应 | 通过 |
| 原文链接 | `https://arxiv.org/abs/2602.07308v1` 和 `https://arxiv.org/abs/2503.12479v1` 均在 Edge 中打开到对应论文页 | 通过 |
| 刷新 | 证据卡片、标题、摘要和链接保持 | 通过 |
| 新建会话 | 旧证据卡片清空，问题为空，课程恢复 `AUTO` | 通过 |
| 学生端/教师端/研究工作台/管理员页 | 页面加载正常，无应用加载错误；管理员游客状态正确拒绝权限 | 通过 |
| 外部来源重复 | 卡片来源唯一；同一来源在回答正文中多次引用表示多个结论复用同一证据，不重复生成来源卡片 | 通过 |
| Mock 边界 | 本地 Mock 或后备结果仍由 UI 明确标记，不作为真实发布能力或发布证据 | 通过 |
| 停止后的空结果 | 教案任务在模型等待/人工审批 checkpoint 阶段被停止；刷新后显示“已停止”和“未生成新回答”，不再伪装为“已完成” | 通过 |
| 教案/作业任务 | 教案任务正确路由到 `TEACH_01_LESSON_PREP_V1` 并进入审批 checkpoint；游客账号无审批权限，未绕过授权，随后安全停止并复测 | 需授权账号继续 |
| 文件/结构化数据 | Edge 文件选择器可以打开，但当前浏览器控制权限拒绝注入本地 fixture（`Not allowed`），未伪造上传成功 | 环境阻断 |
| 暂停/恢复 | Edge 控制面板显示暂停；请求短暂 pending 后状态变为“已暂停”，点击恢复后从 checkpoint 继续并完成；证据不足时明确返回无可核验证据 | 通过 |
| Edge 断开/重连 | 关闭 Edge 测试标签后重新打开工作台，历史会话保留；选择运行任务后恢复回答面板、任务状态和结果 | 通过；初始加载存在短暂恢复窗口 |

Edge 控制台未发现应用 JavaScript error；仅有 KaTeX 对中文字符的兼容性
warning。该 warning 不阻断证据卡片或链接，但应在后续单独处理。

## Runtime 发布边界

`check_runtime_readiness_projection.py` 返回 provider-free readiness `valid=true`，
但 `check_runtime_release_preflight.py` 对已验证的 LEARN、TEACH 和 RESEARCH_01/02
Agent 均保持 `release_eligible=false`，原因是缺少：

- 受控、脱敏的 `authorized_paired` structural suite；
- 独立 semantic sidecar；
- 显式 Agent version 和 Runtime plan version 绑定；
- 独立人工发布决定。

因此本记录不能授权任何 Agent 切换到生产 canary/default，也没有进入 RESEARCH_03
迁移或审计阶段。

## 验证命令

```text
python scripts/check_runtime_readiness_projection.py --base-url http://127.0.0.1:8000
python scripts/check_runtime_release_preflight.py --agent-id <agent-id>
python -m ruff check apps/api/tests/test_unified_web_ui.py
node --check apps/api/app/static/debug/workspace.js
python -m pytest apps/api/tests/test_unified_web_ui.py::test_workspace_external_evidence_normalizes_runtime_items_and_deduplicates apps/api/tests/test_task_presentation.py -q --no-cov
```

本次相关回归测试结果为 `18 passed`。全量测试集合仍需单独按文件定位极慢测试，
不能把限时未完成的全量 Pytest 描述为通过。取消态修复后的启动器/前端回归子集为
`29 passed`。新增历史恢复测试后，目标回归子集为 `30 passed`。限时诊断显示 1,450 项按顺序稳定执行，240 秒约完成 6%；主要耗时
来自测试逐个创建完整 `TestClient/app`，尚未改变测试夹具或用更长超时掩盖问题。
