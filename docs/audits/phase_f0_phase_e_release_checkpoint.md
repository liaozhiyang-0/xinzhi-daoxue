# Phase F0：Phase E Release Checkpoint

## 结论

Phase E final release 已远端保存，Phase F 从该 SHA 创建：

| 项目 | 结果 |
| --- | --- |
| Phase E branch | `agentic/phase-e-experience-memory` |
| Phase E SHA | `4af256980b45c05b7ec39573b848ba5d6b343da6` |
| Phase E commit | `feat(agent): complete phase E experience memory` |
| Phase E backend-ci | Run `32585275518`，SUCCESS |
| frontend job | `97060586870`，PASS |
| backend test job | `97060586951`，PASS |
| Phase F branch | `agentic/phase-f-evaluation-loop` |

Phase E CI 包含 Ruff、Mypy、Pytest、repo drift、OpenAPI、TypeScript drift、配置、敏感文件、benchmark、shell 和 Docker 校验，均 PASS。

独立的 `model-evaluation` Run `32585274930` 为 `jobs=[]`，`gh run view --log-failed` 返回 `log not found`；它不是 Phase E 的 backend-ci 回归，不作为 Phase F release 阻断依据。

## 已建立的 baseline

Phase E full-suite 本地记录为 `1925 passed, 15 skipped, 6 failed`。6 个历史失败按来源归为：

- commercial scenario coverage；
- offline embedding fixture；
- external source count；
- revoked-material text encoding；
- demo scenario count（其中包含多个独立断言失败）。

它们未触及 Experience Memory 或其 migration，Phase F 继续单独记账，不把它们归因给 Phase F。

## F0 交付状态

F0 完成；本阶段没有单独 commit，继续 F1。
