# H0 Harness + Circuit Baseline

日期：2026-08-25  
基线 commit：`5cb699c63bdccdfe454b12d40f399865954d2780`  
分支：`refactor/platform-modernization`

## 基线边界

本阶段未修改 Solver、Runtime、Planner、TaskEvent 或 Circuit 主线。开始检查时
工作区已有未跟踪的审计/阶段文档和 `ci-artifacts/`；这些内容未被本阶段删除或覆盖。

Baseline Set 已按 H0 要求建立：

- 文字题：`TXT-01` 至 `TXT-05`，沿用 `evaluation/demo_cases/text_cases.md`。
- 单图片题：`IMG-01` 至 `IMG-05`，沿用 `evaluation/demo_cases/image_cases.md`。
- 多图题：`MIMG-01` 至 `MIMG-03`，使用 `evaluation/cases/expanded_benchmark_v2/attachments/diagram_00.png`、`diagram_01.png`、`diagram_02.png`。
- 短追问：`FUP-01` 至 `FUP-03`，覆盖结果澄清、重算和资料边界追问。
- 六个业务场景：`COMMERCIAL_FACULTY_001`、`COMMERCIAL_ASSESS_001`、`COMMERCIAL_LEARNING_001`、`COMMERCIAL_FRONTIER_001`、`COMMERCIAL_DATA_001`、`COMMERCIAL_GOVERNANCE_001`，来源为 `evaluation/cases/commercial_scenarios/six_scenarios.yaml`。

矩阵是后续回归的固定输入集合；本阶段只对 H0 要求的四条工作台 smoke 路径进行真实浏览器执行，未把未运行矩阵项描述为已通过。

## 基线保护测试

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_academic_solver_runtime.py -k "does_not_replan_after_provider_timeout" -q
```

结果：`1 passed, 7 deselected`。

该测试确认 `provider_timeout → fail`，`fake.calls == 1`，且 `run.iteration == 0`；这是
`5cb699c` 已修复行为，后续阶段不得改变。

## 浏览器 smoke

使用 Edge 中与 `/workspace` 精确匹配的真实标签页：
`http://127.0.0.1:8000/workspace`。

| 路径 | 实测证据 | status / answer | waiting_review / degrade | latency |
| --- | --- | --- | --- | --- |
| 图片 Solver | 既有真实会话显示“题目原图 1”、答案正文和执行控制 | 已完成，答案存在 | 页面显示“建议复核”；保留图像读数/假设复核边界 | 页面未公开毫秒值 |
| 文字 Solver | 新会话提交 10V 串联 2Ω、3Ω，页面显示 KVL 与 `I = 2 A` | 已完成，答案存在 | 页面显示“建议复核”；执行路径为后备路径 | 页面未公开毫秒值 |
| 通用问答 | 新会话解释傅里叶变换，页面显示课程资料引用与答案 | 带提示完成，答案存在 | 未显示错误；执行路径为后备路径 | 页面未公开毫秒值 |
| 短追问 | 在同一会话追问离散序列频域幅度，页面生成第二条用户消息和回答 | 已完成，答案存在 | 明确标注证据不足和缺失信息 | 页面未公开毫秒值 |

浏览器结果只记录可见页面状态；没有从页面推断隐藏的 agent ID、provider latency 或准确率。

## H0 判定

H0 通过：基线 commit、超时不重试保护、四条工作台 smoke 和 Baseline Set 均已记录。
后续阶段仍必须独立测试、浏览器实测并单独 commit；任一阶段失败立即停止。
