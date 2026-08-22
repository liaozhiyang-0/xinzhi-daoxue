# Phase F7：Full Suite 与 Evidence Campaign

## 执行入口

现有评测仍由唯一入口执行：

```powershell
.\.venv\Scripts\python.exe scripts/run_evaluation.py --validate-only
.\.venv\Scripts\python.exe scripts/run_evaluation_loop.py `
  --report evaluation/reports/latest.json `
  --case-root evaluation/cases `
  --historical-records docs/audits/phase_f7_historical_failure_records.json `
  --expected-case-count 336
```

`run_evaluation_loop.py` 只分析既有 SuiteReport；默认不写文件、不执行 Provider、不生成生产变更。

## 当前证据

| 项目 | 结果 |
| --- | --- |
| 公开 case catalog validation | PASS，84 cases，4 个课程 |
| loop smoke / historical import | PASS，1 个现有 report + 6 个脱敏历史 timeout records |
| failure attribution | 6 条历史 infrastructure/timeout failure |
| pattern aggregate | 5 个带 transient guardrail 的 pattern |
| real Provider evidence | 未包含 |
| 私有 336-case catalog | 当前工作区不可用 |
| production quality claim | 禁止 |

历史失败来源为已提交的定向测试报告，导入文件只保留 case ID、stage、error、版本/证据引用等 bounded metadata。timeout/infrastructure pattern 被明确禁止直接转为长期策略。

## F7 结论

公开等价套件、历史失败归因和闭环结构已接入；私有 336-case 与 real-provider campaign 仍是条件性证据缺口，Phase F 状态为 `STRUCTURAL_GO / CONDITIONAL_GO`，不虚报真实自我优化能力。
