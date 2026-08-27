# 06 Git 提交与今晚收口要求

# 一、开始前

执行：

```bash
git status
git branch --show-current
git rev-parse --short HEAD
```

记录基线。

不要修改 main。

不要：

```bash
git reset --hard
git clean -fd
git push --force
```

---

# 二、修改过程

共享框架修改前先记录影响范围。

每完成一个逻辑阶段：

```bash
git diff --check
```

保持工作区可解释。

不要把：

- debug dump
- 临时截图
- 大型测试输出
- secret
- .env

加入提交。

---

# 三、提交前必须检查

```bash
git status
git diff --stat
git diff --check
```

运行：

- 本轮涉及的定向 Pytest；
- 六场景 smoke；
- 核心 multimodal tests；
- core context/memory tests；
- Runtime/state tests；
- JS syntax check；
- Ruff（变更 Python 文件）；
- 能运行的其他既有门禁。

如果某个测试受已知环境问题阻断：

必须写入 closeout，不得假装通过。

---

# 四、建议 commit 方案

如果改动集中：

```text
fix: harden global runtime context and multimodal reliability
```

如果改动明显分层：

```text
fix: harden shared runtime and capability contracts
fix: stabilize context memory and multimodal flows
test: expand adversarial interaction regression coverage
docs: close out user resilient stability hardening
```

---

# 五、提交后

执行：

```bash
git status
git log -1 --oneline
```

要求：

```text
working tree clean
```

如果测试输出文档按项目惯例需要提交，则一起纳入。

---

# 六、最终向用户报告

必须包含：

```text
1. 最终 commit hash
2. commit message
3. changed files count
4. tests passed / failed / skipped
5. real E2E count
6. major framework fixes
7. remaining known risks
8. whether working tree is clean
```

不要只回复：

```text
完成
```

---

# 七、今晚完成定义

只有：

```text
代码修复
+
回归完成
+
报告完成
+
commit 完成
+
工作区干净
```

才算今晚任务完成。
