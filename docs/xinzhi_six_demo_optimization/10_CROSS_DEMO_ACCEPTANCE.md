# 六大案例统一验收

## 功能
每个案例都必须显示：
任务规划、能力调用摘要、证据/依据、验证/复核、最终结果。
不得泄露内部 CoT。

## 中文
主界面无不必要英文。

## LaTeX
至少30个公式 fixture。

## 场景测试规模建议
- 智能备课：8–12
- 首错诊断：12–20
- 学习路径：8–12
- 科研简报：8–12
- 知识治理：8–12
- 电路诊断：15–25
合计约60–90。

每类至少包含：
normal / incomplete / boundary / degraded / already-correct-or-no-action。

## 答辩主案例
1. 模电电路诊断
2. 首错诊断
3. 科研证据简报

快速展示：
学习路径、智能备课、知识治理。

## 回归
- 普通自由问答不受 Demo mode 影响；
- DemoExamplePicker 只填输入，不注入结果；
- Debug 与 Demo 隔离；
- Task API 不依赖 Demo；
- 真实 Agent 流程仍执行。
