# Git Commit 与回滚纪律

目标：避免“一次改太多 → 多处 Bug → 不知道来源 → 大回滚”。

每阶段必须单独 commit：

H1 `feat(obs): add runtime trace projection`
H2 `feat(eval): add semantic quality evaluators`
H3 `refactor(capability): add descriptive capability specs`
C0 `test(circuit): harden circuit rendering baseline`
C1 `feat(circuit): integrate opt-in circuit render capability`
C2 `feat(circuit): persist rendered circuits as artifacts`
C3 `feat(circuit): add conservative automatic render policy`
C4 `feat(web): present circuit artifacts in solver results`
H4 `feat(tooling): add circuit tool guard pilot`

每个 commit 前：
```bash
git status
git diff --check
```

然后运行 Target Tests + 六场景 smoke + 浏览器 smoke。

回滚原则：
一个阶段一个 revert。

例如 C2 出问题：
```bash
git revert <C2_commit>
```

Circuit 出现问题优先：
`CIRCUIT_RENDER_ENABLED=false`

禁止：
git reset --hard
git push --force
大范围 squash 失去阶段边界

最终返回：
all phase commits
final HEAD
tests
browser E2E
working tree status
remaining risks
