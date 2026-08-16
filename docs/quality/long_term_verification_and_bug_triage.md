# 长期检测、回归测试与 Bug 定位工作协议

状态：启用
版本：quality-ops.v1
统一缺陷台账：docs/quality/bug_backlog.yaml
运行产物目录：.local_outputs/quality/（不提交 Git）

## 目标

持续发现并定位：

1. 代码、配置、数据库迁移和 API 合同回归；
2. Agent Runtime 的任务生命周期、节点顺序、重试、暂停、恢复和 SSE 重连问题；
3. Provider、RAG、工具、降级和敏感信息边界问题；
4. 前端/后端接口不一致、演示边界漂移和提交材料不一致；
5. 真实 Provider 误调用、Mock/合成结果冒充真实结果的问题。

默认所有检查离线、Mock 或 dry-run。不得修改冻结的 SOLVER_CT v1.0 或 SOLVER_CT_V1，不得写入密钥、学生隐私或历史基线原始输入。

## 统一位置与记录原则

- 唯一长期台账：docs/quality/bug_backlog.yaml。
- 每次检测的 stdout、stderr、JSON 报告和截图写入 .local_outputs/quality/<run_id>/。
- 台账只保存可审计摘要、复现命令、证据路径和修复验收条件，不保存敏感内容。
- 发现重复问题时更新已有条目，不新建重复条目；唯一性优先使用 bug_id，其次使用“命令 + 失败签名 + 受影响路径”。
- 另一个进程正在修改的文件不得直接覆盖。先记录 git status --short，把 affected_paths 和 conflict_risk 写入台账。

## 检测分层

### L0：每次改动后的快速门禁

目标是快速发现明显错误；不调用网络、不调用真实模型。

    $env:APP_ENV = "test"
    $env:DEFAULT_AGENT_PROVIDER = "mock"
    $env:ALLOW_MOCK_FALLBACK = "true"
    .\.venv\Scripts\python.exe scripts\validate_config.py
    .\.venv\Scripts\python.exe scripts\check_sensitive_files.py
    .\.venv\Scripts\python.exe -m ruff check .
    git diff --check

失败时先记录 Bug，再决定是否修复；禁止用 git reset --hard、git checkout -- 或删除工作树清除失败。

### L1：每次提交或合并前的合同回归

    .\.venv\Scripts\python.exe -m pytest apps/api/tests/test_contracts.py apps/api/tests/test_task_creation_is_non_blocking.py apps/api/tests/test_task_state_transitions.py apps/api/tests/test_sse_event_order.py apps/api/tests/test_sse_reconnect.py apps/api/tests/test_task_router.py apps/api/tests/test_agent_registry.py -q --no-cov

必须验证：任务创建非阻塞；Provider 不在路由内同步执行；SSE sequence 单调且可重连；未注册/未发布/未配置 Agent 不得执行；SOLVER_CT_V1 输入和 Provider 链路不漂移。

### L2：Runtime 改造后的专题回归

Runtime、迁移、任务执行边界或控制协议变化后执行：

    .\.venv\Scripts\python.exe -m pytest apps/api/tests/test_runtime_*.py -q --no-cov
    .\.venv\Scripts\python.exe -m pytest apps/api/tests/test_runtime_uses_routed_agent.py apps/api/tests/test_task_executor_reliability.py apps/api/tests/test_task_idempotency.py apps/api/tests/test_task_retry.py apps/api/tests/test_sse_reconnect.py -q --no-cov

必须覆盖：正常完成、Provider 失败、限次重试、取消、等待用户输入、等待审批、暂停/恢复、进程重启后的恢复、重复提交幂等、子 Run 归属、checkpoint/observation 可重放，以及异常时不把 waiting_* 错误转换为 failed。

### L3：每日离线一致性审计

    .\.venv\Scripts\python.exe scripts\validate_scenarios.py
    .\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py
    .\.venv\Scripts\python.exe scripts\validate_external_sources.py
    .\.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
    .\.venv\Scripts\python.exe scripts\validate_contest_cases.py
    .\.venv\Scripts\python.exe scripts\validate_completed_workflows.py
    .\.venv\Scripts\python.exe scripts\audit_readiness_consistency.py

重点关注 Agent、场景、课程和意图是否串线；synthetic/private/real 标记是否一致；提交材料是否把未核验演示写成真实效果；外部来源是否仍有 metadata-only 和人工复核门。

### L4：每日或每晚完整质量检查

确认没有其他进程占用工作树、数据库或测试资源后执行：

    .\scripts\check.ps1

该命令包含配置、敏感文件、Ruff、Mypy、Pytest、OpenAPI 导出、Docker Compose 配置和 Git whitespace 检查。Docker 不可用时记录 verification_blocker，不能描述为通过。

Mypy 或 Pytest 超过 10 分钟没有完成时：

1. 记录命令、开始时间、进程状态和超时信息；
2. 不杀掉无法确认归属的其他 Python/测试进程；
3. 分拆到 L1/L2 专题测试定位；
4. 使用 needs_recheck，不能写成 passed 或 failed。

### L5：每周耐久性与恢复检查

仅使用本地 Mock、合成输入和隔离数据库：

- 运行有界 soak/e2e，检查任务创建、SSE、重试、恢复和资源释放；
- 在隔离数据库上验证 Alembic upgrade、最新 schema、空库初始化和回滚策略；
- 生成 Runtime trace/replay 报告，检查 event sequence、run lineage、checkpoint 和敏感字段脱敏；
- 比较上一周失败数、重试数、恢复数、超时数和未分类异常数；不虚构准确率或性能提升。

## Bug 分级与状态

严重度：

- P0：数据损坏、跨用户/跨课程泄露、凭据泄露、任务不可控执行、冻结基线破坏。
- P1：主链路不可用、任务无法恢复、SSE/迁移/API 合同破坏、CI/发布门禁失败。
- P2：单一 Agent/场景/浏览器路径失败，存在降级但影响验收或用户体验。
- P3：文档、可观测性、提示或非关键体验问题，不阻断主流程。

状态：

observed → triaged → in_progress → fixed_pending_verification → verified → closed

特殊状态：

- blocked_external：等待教师审核、官方规则、真实 Provider 授权或外部数据；
- needs_recheck：检测超时、环境不完整或与其他进程竞争，尚不能判断为代码缺陷；
- duplicate：关联已有 Bug ID；
- wont_fix：记录理由和替代保护措施。

## 每条 Bug 必须包含

    bug_id: BUG-YYYYMMDD-NNN
    kind: code_bug|contract_bug|config_bug|test_failure|verification_blocker|governance_gap
    severity: P0|P1|P2|P3
    status: observed|triaged|in_progress|fixed_pending_verification|verified|closed|blocked_external|needs_recheck|duplicate|wont_fix
    title: 一句话描述
    detected_at: ISO-8601 时间
    detected_by: 进程或负责人
    first_seen_command: 可复制命令
    failure_signature: 稳定、可去重的错误摘要
    affected_paths:
      - 相对路径
    evidence:
      - 相对 .local_outputs/quality/... 的证据路径
    reproduction:
      preconditions: 环境、开关、输入
      steps:
        - 步骤
      expected: 预期行为
      actual: 实际行为
    conflict_risk: none|read_only|active_worktree|external_dependency
    owner: null
    suggested_fix: 最小修复方向
    regression_test: 新增或已有测试路径
    verification_command: 修复后命令
    resolved_at: null
    notes: 不能证明的内容必须明确写出

## 修复闭环

1. 检测进程只负责复现、定位、记录和提供证据，不顺手修改未授权代码。
2. 修复进程领取 Bug 后先确认工作树冲突、冻结边界、凭据和真实 Provider 限制。
3. 修复必须包含最小回归测试，或说明为什么只能通过配置/人工审核验证。
4. 修复后先跑对应 L1/L2，再跑 L0；资源允许时执行完整 check.ps1。
5. 只有证据路径、命令和结果齐全，才从 fixed_pending_verification 改为 verified；负责人确认后才改为 closed。
6. 新增 Runtime 节点、Agent、Provider、迁移或事件协议时，必须更新测试矩阵和台账。

## 给另一个进程的明确任务

1. 先读取 docs/quality/bug_backlog.yaml，不重复创建已有条目。
2. 先执行 L0 和相关 L1/L2，只读定位当前问题。
3. 将所有失败写入台账，证据放入 .local_outputs/quality/。
4. 只修复 owner 明确分配且 conflict_risk 已确认的条目。
5. 对每个修复增加回归验证并更新 verification_command。
6. 不修改 SOLVER_CT v1.0、SOLVER_CT_V1、.local_inputs/、真实凭据和其他进程未交接的文件。
7. 最终报告列出：Bug ID、修改文件、执行命令、通过/失败/跳过、未解决风险和下一轮建议。

