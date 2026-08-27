# 01 测试治理与基线冻结

开始前记录：
```bash
git status
git branch --show-current
git rev-parse HEAD
git describe --tags --always
```

记录 stable baseline、runtime generation、canonical plan version、production fingerprint、active planner/runtime、handler/capability/tool hash。

若存在 dirty changes，分类为 TEST_LOG / TEST_FIX / PREEXISTING / GENERATED / UNKNOWN；UNKNOWN 不得混入最终提交。

建立永久 Golden Set：
- General 10
- CT 15
- AE 10
- DE 10
- SS 10
- RAG 10
- 单图 10
- 多图 10
- Circuit 20
- 长会话 5

优先使用用户本地真实题目和电路图。

任何修复后至少重跑：当前失败 cluster + Golden Set。

输出：
`docs/audit/68_soak_test_baseline.md`
