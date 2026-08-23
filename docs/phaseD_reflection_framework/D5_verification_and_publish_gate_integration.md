# Phase D5：Verification 与 Publish Gate 融合

## 目标
建立清晰权威顺序，防止 Critic pass 覆盖确定性错误。

## 最终原则
- deterministic failure 不得被 Critic pass 覆盖；
- citation/evidence failure 不得被 Critic pass 覆盖；
- permission/side-effect failure 不得被 Critic pass 覆盖；
- Revision 后重新验证；
- 最终发布仍由 Result Governance / Completion 边界决定。

## Issue Taxonomy
尽量复用现有 error codes，统一映射：
reasoning、numerical、unit、factual、missing_evidence、citation、scope、format、safety、tool_conflict、unsupported_claim、incomplete_solution。

## 场景
Academic Solver：domain verification 优先。
Knowledge：evidence/citation gate 优先。
Research：provenance/unsupported claim 优先。
Teaching：pedagogical quality 可由 Critic 评估，事实仍走 evidence/domain gate。

## 提交
本阶段不 commit，完成后继续 D6。
