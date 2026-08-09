# `LEARN_01_LOCAL_RETRIEVAL_V1` Runtime 合同评测

## 目的

本评测为 `LEARN_01_LOCAL_RETRIEVAL_V1` 建立 provider-free Runtime 合同边界。
它验证的是 Runtime 的生命周期与结果门禁，不是本地知识库检索质量、模型回答准确率或
真实 Provider 的可用性。

评测只使用 `apps/api/tests/test_knowledge_qa_runtime.py` 中已有的
`FakeKnowledgeQA`，并在测试文件内用最小子类补充 artifact 场景。测试不会访问网络、
真实模型、真实 Provider 或真实凭据。

## 当前合同

当前 Runtime 计划是一个固定的两节点计划：

```text
knowledge.execute -> knowledge.verify
```

- `knowledge.execute` 调用本地 Knowledge QA fake，并把结果、证据数量和 artifact ID
  写入有界 observation。
- `knowledge.verify` 校验结果状态、回答内容、retrieval mode、证据状态以及
  citation/artifact 门槛。
- 验证失败会将 verification 节点置为 `partial`，Controller 随后将 Run 置为
  `failed`，因此失败结果不会提交为 Runtime 成功。只有显式设置
  `knowledge_qa_runtime.replan_on_verification_failure=true` 时，证据不足或引用
  缺失才会进入一次受限的用户补充信息流程；默认行为仍然是直接 fail-closed。
- 通过时，两个节点均为 `succeeded`，Run 才能进入 `completed`。

“证据充分”不是单独的成功条件。`evidence_status` 为 `sufficient` 或 `complete` 时，
还必须至少存在一个 citation 或 artifact；否则以
`knowledge_citations_missing` fail-closed。`insufficient` 或 `none` 以
`knowledge_evidence_insufficient` fail-closed。

## 覆盖矩阵

| 场景 | 预期 Runtime 结果 |
| --- | --- |
| execute 成功，verify 通过，且有 citation | `completed` |
| execute 成功，verify 通过，且无 citation 但有 artifact | `completed` |
| 证据不足 | verification=`partial`，Run=`failed` |
| 证据充分但无 citation/artifact | verification=`partial`，Run=`failed` |
| mode 非允许值或回答为空 | verification=`partial`，Run=`failed` |
| execute/verify 顺序 | 只出现 `knowledge.execute` 后 `knowledge.verify` |
| 显式 opt-in 且验证失败 | Run=`waiting_input`，等待有界 `query`/`text` |
| 补充信息后重规划 | 同一 Run 的 `iteration=1`，执行版本化 `.replan.1` 计划 |
| 无效补充信息或预算耗尽 | Run=`failed`，不重复调用检索 |

## 明确不宣称的能力

该合同证明的是固定 `execute -> verify` 生命周期，以及显式 opt-in 时的单次、预算受限
`ASK_USER -> REPLAN -> execute -> verify` 路径。它不是无界自主循环：只有证据不足或引用
缺失触发补充信息，输入只允许有界的 `query` 或 `text`，默认配置不改变，且预算/输入校验
失败时保持 fail-closed。它也不能作为“Knowledge QA 已经具备通用自主 replan”或“已经是
完全自主 Agent”的证据。

同理，fake 通过只证明协议与门禁行为可重放；不证明真实检索召回、引用正确性、回答
准确率、Provider 延迟或生产默认发布资格。生产发布仍需要授权的真实成对 trace、语义
评测和现有 release gate。

## 复现命令

在仓库根目录执行：

```powershell
.venv\Scripts\pytest.exe -q --no-cov apps/api/tests/test_knowledge_qa_runtime_contract.py apps/api/tests/test_knowledge_qa_runtime_replan.py
.venv\Scripts\ruff.exe check apps/api/tests/test_knowledge_qa_runtime_contract.py
```

预期 pytest 为 7 个测试通过（参数化场景展开后），且不发生真实 Provider 调用。
