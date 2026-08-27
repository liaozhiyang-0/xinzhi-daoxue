# Codex 下一阶段总执行指令

读取并严格执行本目录全部文档，以本文件为总纲。

当前阶段名称：

> Capability Quality Hardening

不要进行新一轮大架构重构，也不要回到单点补丁式修复。

当前重点：

1. 多图语义理解；
2. 长上下文 / WorkingState / Memory / 用户纠错；
3. 通用回答 fallback；
4. 独立 data_analysis 能力收敛；
5. 专业答案语义正确性；
6. Semantic Validator；
7. 真实本地题库资产复用；
8. 全局回归和 Git 提交。

## 第一原则：优先利用本地真实题库

用户本地已经有大量现成电路图和题目。

先按 `01_local_asset_discovery.md` 只读扫描项目及已配置数据目录，建立真实题库索引。

禁止删除、移动、改名、覆盖、批量复制原始用户素材。

多图理解和 Semantic Benchmark 优先从真实资产中抽样组合，不要主要依赖人工生成的简单测试图片。

## 第二原则：修改共享根因

任何问题先判断属于：

Scenario / Task Contract / Multimodal / Context / WorkingState / Memory / Router / Provider Capability / Runtime / Semantic Validator / Presentation

中的哪一个共享层。

禁止针对具体 Agent、图片数量、具体题目写特殊分支。

## Phase 1：真实资产发现

生成：

- `docs/audit/28_local_asset_inventory.md`
- `docs/audit/29_real_asset_test_manifest.md`

## Phase 2：多图语义

验证：

- 全部图片是否被消费
- 图片顺序是否正确
- 图之间关系是否正确
- 用户指代是否正确
- 角色是否正确
- 图文冲突是否识别

Provider 不支持多图时必须由统一 Multimodal Orchestrator 降级处理。

目标：

- silent image drop = 0
- image reorder = 0

## Phase 3：长上下文

验证 20~30 turns：

- latest explicit correction
- working state
- short follow-up continuity
- session isolation
- compaction
- image references
- response preference

用户最新纠正必须高于旧 summary / memory。

## Phase 4：General Answer

取消独立数据分析产品能力。

保留 legacy `data_analysis` intent，但映射到 General Academic Answer。

普通数据分析、趋势解释、实验数据理解由通用回答完成。

不要再返回功能冻结 409。

如果没有调用正式统计工具，不得虚构正式显著性结论。

## Phase 5：Semantic Validator

建立可组合检查：

- NumericCheck
- UnitCheck
- SymbolCheck
- KeyPointCheck
- CitationCheck
- AttachmentCoverageCheck
- InstructionFollowingCheck

优先扩展已有 Validator / Evaluation 框架，不要另造大型平行系统。

## Phase 6：专业 Benchmark

优先利用本地真实题库建立：

- CT 30
- AE 30
- DE 30
- SS 30

真实资产不足再补现有 benchmark / fixture。

评分使用 A/B/C/D。

普通题 A+B >= 95%，困难题 A+B >= 90%。

不能为 benchmark hardcode。

## Phase 7：共享修复

遵循：

Observed Failure
→ Shared Root Cause
→ Architecture/Capability Gap
→ Global Fix
→ Contract Test
→ Target Regression
→ Six Scenario Smoke

共享层修改前必须做影响分析。

## Phase 8：最终回归

执行：

- 六场景 smoke
- 多图真实资产 E2E
- 长对话
- General Answer
- Semantic Benchmark
- Runtime/State contract

## Phase 9：Git 提交

关键回归通过后提交。

推荐：

`fix: harden multimodal context and semantic answer quality`

不要自动 push，除非当前仓库流程已有明确要求。

最终必须返回：

- commit hash
- commit message
- tests
- real asset count
- multi-image result
- long-context result
- semantic benchmark
- major framework fixes
- remaining risks
- working tree status

## 最终目标

系统不应该只是“六个场景稳定运行”，而应该进一步达到：

> 用户可以直接拿本地真实专业题、多张电路截图、长对话、纠正后的条件和自由问题来使用，系统仍能保持上下文、理解图像关系、选择合适能力并给出可靠答案。
