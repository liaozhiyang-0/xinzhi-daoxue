# CI 与评测闭环

## 概览

代码改动通过 GitHub Actions 自动验证；真实模型评测与日常 CI 完全隔离，
不会因缺少 API Key 或成本问题阻塞开发。

| 工作流 | 触发时机 | 内容 | 报告 |
| --- | --- | --- | --- |
| `backend-ci`（test job） | push / PR | 本地评测集全量运行 | `ci-artifacts/`（pytest junit、drift JSON/MD、CI 摘要） |
| `backend-ci`（frontend job） | push / PR | 前端 typecheck / build / smoke + OpenAPI 合同漂移检查 | `frontend-build` artifact |
| `model-evaluation`（offline 任务） | 每日 03:30 UTC + 手动 | 纯本地评测（mock provider，零成本） | `evaluation/reports/latest.json/md` 上传为 artifact |
| `model-evaluation`（live 任务） | 仅手动，且已配置付费 Key | 真实模型评测，硬性成本上限 | `evaluation/reports/live/<时间戳>/` 单独保存 |

## 前端工程化与类型合同

- TypeScript 边界模块在 `apps/web/src/`，构建产物输出到
  `apps/api/app/static/debug/ts/`（`npm --prefix apps/web run build`）。
- `scripts/generate_openapi_types.py` 从导出的 OpenAPI
  （`docs/api/openapi.json`）生成 `apps/web/src/api-types.ts`；
  `apps/web/src/api-contract-check.ts` 在编译期校验手写前端合同
  （如 `StudentTaskPayload`）仍可赋给后端生成类型。
- CI 的 frontend job 执行 `npm ci` → typecheck → build → smoke，
  并用 `git diff --exit-code` 校验 `api-types.ts` / `openapi.json` 无漂移。
- 本地重新生成类型：`npm --prefix apps/web run gen:api-types`。

## 本地评测集（纯本地、无外部模型）

运行在 `backend-ci` 与 `scripts/check.ps1` 中的检查：

- 路由回归：`scripts/run_regression.py` + pytest 路由用例
- 任务协议 / SSE 契约：`apps/api/tests/test_sse_events.py`、`test_sse_event_order.py`
- 配置校验：`scripts/validate_config.py`
- 敏感文件检查：`scripts/check_sensitive_files.py`
- 仓库目录漂移检查：`scripts/check_repo_drift.py`（清单在 `config/repo_layout.yaml`）
- Docker Compose 校验：`docker compose config --quiet`
- 静态检查：Ruff、Mypy
- 评测案例校验：`scripts/run_evaluation.py --validate-only`

本地一键执行：

```powershell
.\scripts\check.ps1
```

## 真实模型评测隔离

- 日常 CI 环境固定 `DEFAULT_AGENT_PROVIDER=mock`、`XINGCHEN_ENABLED=false`；
  所有 `requires_api_key` 标记的测试默认跳过（`RUN_REAL_MODEL_TESTS=1` 才启用）。
- `model-evaluation` 的 live 任务仅在手动触发**且**已配置付费 Key secret 时运行；
  使用 `--live --confirm-paid --max-cases 3` 硬性限制成本（默认最多 3 条案例）。
- live 报告写入 `evaluation/reports/live/<时间戳>/`，与日常结果分开，
  不会混入 CI 日常产物；离线报告固定 `mode: offline`，禁止冒充真实结果。

## 评测报告与基线对比

`scripts/run_evaluation.py` 输出统一 JSON + Markdown 报告：

- `evaluation/reports/latest.json` / `latest.md`
- 记录：模式（`mode`）、起止时间、`run_id`、案例/目录 SHA-256、
  schema 版本、每条案例的 `evaluation_mode`、维度得分、失败阶段与错误类型。

与历史基线对比：

```powershell
.\.venv\Scripts\python.exe scripts\compare_evaluation_reports.py `
  evaluation\reports\baseline.json evaluation\reports\latest.json
```

缓存与续跑：默认复用缓存；`--no-cache` 强制重跑，`--rerun-failed` 只重跑失败案例。
新增案例必须先 `--validate-only`，再离线单条验证；不得用降低期望的方式提高通过率。
