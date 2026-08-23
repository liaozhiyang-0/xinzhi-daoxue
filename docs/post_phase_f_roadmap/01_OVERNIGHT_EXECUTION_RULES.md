# Codex 半夜无人值守执行总规则

## 目标

在用户不持续参与的情况下，安全执行 Phase G-K。

---

## 一、开始前

必须检查：

```text
git status
git branch --show-current
git log --oneline -10
git remote -v
```

确认：

- Phase F 已完成；
- Phase F release 已保存；
- 当前工作树已记录；
- 不覆盖 unrelated user changes。

---

## 二、允许自主调整

Codex 可以调整：

- 类名
- 文件名
- 内部目录
- 测试脚本组织
- 数据结构细节
- 报告结构
- fixture 数量
- evaluation threshold 的合理默认值

但是不能改变：

```text
真实验证
→ 大规模测试
→ 失败聚类
→ 定向优化
→ Replay
→ Regression
→ Release
```

这一主线。

---

## 三、禁止

禁止：

- force push
- reset --hard
- clean -fd
- 自动 merge main
- 自动部署 production
- 自动开启 canary
- 自动修改 API key / secret
- 删除历史 benchmark
- 修改评分阈值掩盖失败
- 为提升分数删测试
- 将 synthetic 结果宣传为 real-provider
- 无预算地大量调用付费模型

---

## 四、阶段间推进

每个大阶段：

```text
execute
→ local targeted tests
→ full relevant tests
→ report
→ one commit
→ push
→ CI
```

只有：

```text
critical regression = 0
```

才自动进入下一大阶段。

---

## 五、失败处理

### 当前阶段相关失败

做最小修复，再测。

最多允许：

```text
2 个 fix cycles
```

仍失败则停止。

### 历史失败

记录：

- test
- reason
- baseline commit
- relation to current phase

不要擅自大改。

---

## 六、真实 Provider

没有 key：

```text
SKIP
```

有 key 但没有预算：

```text
SKIP
```

有预算：

只运行明确上限的 representative subset。

---

## 七、最终输出

Codex 整夜结束时生成：

```text
docs/audits/overnight_execution_summary.md
```

包含：

- 完成哪些 Phase
- 每阶段 commit SHA
- CI
- Benchmark 结果
- Top Failure Patterns
- 优化内容
- 回归
- Provider 成本
- 未完成项
- 下一步建议
