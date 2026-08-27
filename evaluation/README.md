# Evaluation assets

本目录是当前仓库的离线评测资产集合，不是单一运行时模块。

## 目录职责

- `cases/`：按能力、课程和场景组织的评测输入；
- `schemas/`、`rubrics/`、`manifests/`：案例结构、评分规则和数据集清单；
- `runtime_cases/`、`automatic_routing/`、`targeted/`：Runtime、自动路由和专题回归输入；
- `circuit_theory/`、`knowledge_retrieval/`、`math/`、`math_circuit/`：领域专项案例、schema、脚本及已标注结果；
- `model_agents/`、`demo_cases/`：模型/Agent 映射和演示案例；
- `baselines/`：明确标注的基线与当前系统 manifest；
- `private_cases/`：受限案例说明，原始敏感输入不应进入公共仓库；
- `cache/`、`reports/`、部分 `results/`：运行生成物或证据输出，默认保留以便审计，不作为源代码依赖。

## 与目标结构的对应关系

当前仓库保留 `circuit_theory/` 和 `knowledge_retrieval/` 作为自包含 benchmark 包，因为 CI、Dockerfile、脚本和历史证据直接引用这些稳定路径；它们语义上属于 `benchmarks/`，包内 `scripts/` 语义上属于 `runners/`。本轮不做兼容性破坏式搬迁，避免重写评测逻辑。`cases/`、`schemas/`、`rubrics/` 和 `manifests/` 已按目标职责分离；`reports/` 与 `cache/` 仍是被忽略的本地生成物。历史报告暂不移动到新的物理目录，先以现有引用和忽略规则保持可重放，迁移需单独更新 API、CI、Docker 和证据链接。

## 运行边界

评测脚本应使用仓库已有的配置、Provider 和 HTTP 调用链。Mock、synthetic、cached 和 real-provider 结果必须保持显式标记；本地默认使用隔离数据库和离线/Mock 配置。数据分析评测资产仍可用于合同与冻结边界验证，但 `RESEARCH_ANALYSIS` 在 `data_analysis_enabled=false` 时不注册到 Runtime 业务执行表。

常用验证命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py
.\.venv\Scripts\python.exe scripts\validate_scenarios.py
```
