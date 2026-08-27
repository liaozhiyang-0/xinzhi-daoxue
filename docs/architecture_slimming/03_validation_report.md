# 结构收敛验证报告

验证记录：2026-08-26/27。所有结果只描述实际执行的本地命令；未执行的真实 Provider、Docker 容器和全量测试不视为通过。

## 已通过

| 检查 | 实际结果 |
|---|---|
| Ruff | `All checks passed!` |
| Mypy | `Success: no issues found in 362 source files` |
| 结构定向 Pytest | `92 passed, 8 skipped, 2 warnings` |
| Pytest collect-only | `2055 tests collected` |
| 活动 JavaScript 语法 | 17 个文件通过 `node --check` |
| 配置校验 | development/test 配置均返回 `valid: true` |
| 评测案例校验 | 561 个案例通过，均为 synthetic，private publishable violations 为 0 |
| 场景校验 | `valid: true`，10 个场景、9 个启用 |
| 敏感文件检查 | passed |
| 仓库布局检查 | `repo layout matches manifest` |
| 目录清单漂移 | `repository catalog is current` |
| Docker Compose 静态配置 | `docker compose config -q` 通过；未执行 build/up |
| 浏览器页面冒烟 | `/workspace`/`/student` 加载、新建会话、普通问答、课程知识问答、专业电路题、公式渲染、图片上传、科研任务和多轮追问均完成任务提交/结果投影；普通问答明确显示安全降级边界；无 JavaScript error |
| 退役表面探针 | `/workspace-react` 和 `api-types.js` 返回 404；保留模块返回 200 |

## 未执行或有边界的检查

- 没有调用真实付费 Provider，也没有据此声称模型质量或准确率；
- 没有启动 Docker Compose 服务；只验证了 Compose 文件可解析；
- 没有运行完整 2055 项测试，原因是本轮主要是删除死的 React/历史资产和小范围 Runtime 注册条件变更；已完成全量收集和结构定向回归；
- 浏览器任务使用本地测试数据库和 Mock/关闭外部依赖配置，结果不是生产 Provider 证据；
- `git diff --check` 通过，输出的 CRLF 提示是 Windows 换行规范提示，不是 whitespace 错误。
- 课程回答中的 Unicode 圆圈数字 `①` 触发 4 条 KaTeX strict-mode warning（`unknownSymbol`/缺少字体 metrics）；未影响本轮页面或任务完成，但应在后续数学文本规范化中单独处理。
