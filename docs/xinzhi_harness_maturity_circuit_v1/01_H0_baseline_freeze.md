# H0：冻结 5cb699c 稳定基线

开始前执行：

```bash
git status
git branch --show-current
git rev-parse HEAD
```

确认 feature 分支基于：
`5cb699c63bdccdfe454b12d40f399865954d2780`

建立 Baseline Set：
- 5 个普通文字题
- 5 个图片题
- 3 个多图题
- 3 个短追问
- 六个业务场景

优先使用用户已人工确认当前正常的真实题。

记录：
- task status
- agent/capability
- answer existence
- semantic quality
- latency
- waiting_review
- degrade state
- browser display

必须额外保护 5cb699c 已修复行为：
`provider_timeout → fail → 不重复 replan`
并断言 provider call count = 1。

浏览器必须在 `/workspace` 实测：文字 Solver、图片 Solver、通用问答、追问。

输出：
`docs/audit/46_harness_circuit_baseline.md`

未完成基线，不进入 H1。
