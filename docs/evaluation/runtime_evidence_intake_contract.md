# Runtime evidence intake contract

本合同定义 `collect_runtime_canary.py`、
`collect_runtime_semantic_evidence.py` 和
`check_runtime_release_preflight.py` 之间的离线 evidence intake 边界。
它只描述“已经捕获的材料如何被校验和绑定”，不代表仓库已经拥有真实课程
数据、真实 Legacy/Runtime 结果或生产发布授权。

## 不可绕过的输入合同

- 结构套件必须是 `authorized_paired`，并同时绑定 `agent_id`、`agent_version`、
  `runtime_plan_version`、非空 `authorization_ref`、带时区的 `captured_at` 和
  `redaction_status=redacted`。
- 每个 case 必须同时拥有 Legacy payload、Runtime payload 和 checkpoint trace；
  `sequence` 必须连续，`state_version` 必须递增，checkpoint 中的 `AgentRun`、
  `run_id`、`plan.version` 和状态版本必须彼此一致。
- 语义 sidecar 必须逐 case 覆盖结构套件，不能缺 case、重复 case 或增加未知 case；
  sidecar 不保存原始输入，只保存输入、Legacy 输出和 Runtime 输出的确定性 SHA-256。
- 每条语义 judgement 必须具备完整且无额外字段的 dimensions、decision、judge_type、
  rubric_version、reviewer_ref、reviewed_at、redaction_status 和 authorization_ref；
  `reviewed_at` 必须带时区，`redaction_status` 必须为 `redacted`。
- sidecar 的 Agent、Agent 版本、Runtime plan 版本、suite 和 case 必须绑定到结构套件；
  preflight 的 expected version 也必须匹配。
- `synthetic`、缺 suite、缺 sidecar、非法 JSON、证据不完整或任何绑定失败都必须
  fail-closed，`release_eligible` 不得为真。测试中的 fixture 只能证明合同，不是发布证据。

## 真实执行到离线门禁的顺序

真实流程需要由有权限的操作员在仓库外或受控私有目录完成；下面的顺序是操作合同，
本仓库测试不会执行 Provider，也不会制造真实 evidence：

1. 固定 Agent、Agent 版本、Runtime plan 版本、suite ID、case 清单和 rubric 版本，
   并取得可审计的授权引用。
2. 在真实运行环境中逐 case 执行同一输入的 Legacy 路径和显式 opt-in 的 Runtime
   路径；保存脱敏后的结果摘要和 Runtime checkpoint trace。采集阶段必须隔离真实密钥，
   原始输入和凭据不得进入公共仓库。
3. 用 `collect_runtime_canary.py` 读取已捕获的 payload/checkpoint 或 manifest，审计
   checkpoint、校验配对、授权、版本和结构门禁，输出结构 suite。此命令不调用 Provider。
4. 对授权人员提供的脱敏输入和人工/受控评审结果，运行
   `collect_runtime_semantic_evidence.py`；它只输出逐 case 的 hash、审判字段和绑定身份，
   不把原始输入写入 sidecar。
5. 运行 `check_runtime_release_preflight.py --agent-id ... --suite ...
   --semantic-sidecar ... --expected-agent-version ... --expected-runtime-plan-version ...`。
   两个 expected version 必须显式提供；即使 artifact 自身版本互相一致，省略任一参数
   也必须 fail-closed。该命令只离线读取两个 artifact，必须同时通过结构、语义和显式
   版本绑定门禁才返回成功。
6. 将 suite、sidecar、preflight JSON、授权记录和版本信息作为同一 release record 保存到
   受控私有位置；再由独立人工发布流程决定 canary/default。preflight 成功本身不等于
   自动发布，也不替代人工审批。

## 测试边界

`apps/api/tests/test_runtime_evidence_intake_contract.py` 使用明确标注的本地 synthetic
fixture 验证上述拒绝条件、hash 脱敏、checkpoint 审计、case coverage、版本绑定和缺失输入。
这些测试不证明准确率、语义等价、Provider 行为、真实执行成功或生产 readiness；没有授权的
真实 Legacy/Runtime 成对 trace 和离线语义评审时，发布门禁必须保持关闭。
